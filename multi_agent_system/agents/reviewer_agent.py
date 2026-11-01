"""
multi_agent_system.agents.reviewer_agent
======================================
Agent Reviewer: Tiếp nhận task, plan, code đa tệp, testcase, cây thư mục và log lỗi Sandbox.
Thẩm định nguyên nhân cốt lõi và phân định chính xác:
- PLANNER: Lỗi Global (mâu thuẫn giữa các file, sai import, lệch interface)
- CODER: Lỗi Local (cú pháp nội bộ trong 1 file, lỗi logic cài đặt thân hàm)
- TESTER: Lỗi Testcase (assert sai kỳ vọng, testcase vi phạm yêu cầu bài toán)
"""
import os
from pyexpat.errors import messages
from openai import OpenAI
import json
from typing import Dict, Optional, Any, List, Tuple, Set
from .base_agent import BaseAgent
from ..schemas import MultiFilePlan, ReviewDecision, ReviewTarget
from .. import config
import re
from ..tools.workspace_tools import WorkspaceTools

class ReviewerAgent(BaseAgent):
    max_tool_iterations: int = 4

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tool_iterations: int = 4
    ):
        # 1. Gọi super().__init__ trước để khởi tạo self.base_url, self.model_name,...
        super().__init__(
            model_name=model_name or config.REVIEWER_MODEL,
            base_url=base_url,
            temperature=0.1
        )
        
        # 2. Bây giờ self.base_url đã tồn tại và đã được chuẩn hóa rstrip("/")
        self.max_tool_iterations = max_tool_iterations
        self.timeout = config.LLM_TIMEOUT
        
        api_base_url = self.base_url
        if not api_base_url.endswith("/v1"):
            api_base_url = f"{api_base_url}/v1"
            
        self.client = OpenAI(
            base_url=api_base_url,
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
            timeout=self.timeout
        )

    def _truncate_error_log(self, error_msg: str, max_lines: int = 60) -> str:
        """Thu gọn error log quá dài, giữ lại đầu và cuối stacktrace để tránh tràn context."""
        lines = error_msg.strip().splitlines()
        if len(lines) <= max_lines:
            return error_msg
        
        half = max_lines // 2
        return (
            "\n".join(lines[:half]) 
            + f"\n\n... [ĐÃ CẮT BỚT {len(lines) - max_lines} DÒNG LOG KHÔNG QUAN TRỌNG] ...\n\n" 
            + "\n".join(lines[-half:])
        )

    def _detect_text_tool_calls(self, text: str, tools_map: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Bắt trường hợp LLM sinh 1 hoặc NHIỀU dòng text JSON gọi hàm thay vì gửi qua API tool_calls.
        Ví dụ: 
        {"name": "read_file", "arguments": {"file_path": "src/Main.java"}}
        {"name": "read_file", "arguments": {"file_path": "src/bus/EventBus.java"}}
        """
        if not text:
            return []

        detected_calls: List[Tuple[str, Dict[str, Any]]] = []

        # Tách chuỗi theo từng dòng hoặc bắt các block JSON {...}
        json_candidates = []
        for line in text.splitlines():
            line_str = line.strip()
            if line_str.startswith("{") and line_str.endswith("}"):
                json_candidates.append(line_str)

        if not json_candidates:
            # Tìm tất cả các khối JSON qua Regex
            matches = re.findall(r"\{.*?\}", text, re.DOTALL)
            json_candidates.extend(matches)

        for json_str in json_candidates:
            try:
                obj = json.loads(json_str)
            except Exception:
                continue

            if not isinstance(obj, dict):
                continue

            # Trường hợp 1: {"name": "read_file", "arguments": {...}}
            func_name = obj.get("name") or obj.get("function") or obj.get("tool")
            func_args = obj.get("arguments") or obj.get("parameters") or obj.get("args")

            if func_name and func_name in tools_map:
                if isinstance(func_args, str):
                    try:
                        func_args = json.loads(func_args)
                    except Exception:
                        pass
                detected_calls.append((str(func_name), func_args if isinstance(func_args, dict) else {}))
                continue

            # Trường hợp 2: {"action": "read_file", "action_input": {...}}
            action = obj.get("action")
            if action and action in tools_map:
                action_input = obj.get("action_input", {})
                detected_calls.append((str(action), action_input if isinstance(action_input, dict) else {}))

        return detected_calls

    def call_llm(self, prompt: str, format_json: bool = False) -> str:
        """
        Gọi LLM trực tiếp (dùng khi cần prompt đơn lẻ hoặc fallback).
        """
        try:
            kwargs = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
            }
            if format_json:
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            # Nếu LLM không hỗ trợ response_format={"type": "json_object"}, retry không format
            if format_json:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                    )
                    return response.choices[0].message.content or ""
                except Exception as inner_e:
                    print(f"⚠️ [Reviewer] Lỗi call_llm retry: {inner_e}")
            print(f"⚠️ [Reviewer] Lỗi call_llm: {e}")
            return ""

    @staticmethod
    def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        try:
            parsed = json.loads(text.strip())
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    pass
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(text[start:end + 1])
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None
            return None

    def _execute_tool(self, tools_map: Dict[str, Any], func_name: str, args: Any) -> str:
        """Thực thi tool từ tools_map của LangChain."""
        print("\n" + "─"*50)
        print(f"🔧 [Reviewer Tool Call] Tool : {func_name}")
        print(f"📋 [Reviewer Tool Call] Args : {args}")
        print("─"*50)
        tool = tools_map.get(func_name)
        if not tool:
            return f"Lỗi: Không tìm thấy tool '{func_name}'."
        try:
            # LangChain tool hỗ trợ .invoke() (nhận dict hoặc string)
            if isinstance(args, dict):
                result = tool.invoke(args)
            elif isinstance(args, str):
                try:
                    parsed_args = json.loads(args)
                    result = tool.invoke(parsed_args)
                except Exception:
                    result = tool.invoke(args)
            else:
                result = tool.invoke(args or {})
            return str(result)
        except Exception as e:
            return f"Lỗi khi thực thi tool '{func_name}': {str(e)}"

    def _normalize_tool_args(self, args: Any) -> str:
        if isinstance(args, dict):
            return json.dumps(args, sort_keys=True)
        return str(args)

    def review(
        self,
        task_goal: str,
        plan: MultiFilePlan,
        files_dict: Dict[str, str],
        test_cases: str,
        error_msg: str,
        workspace_dir: str
    ) -> ReviewDecision:
        all_project_files = [f.filepath for f in plan.files]
        clean_error_msg = self._truncate_error_log(error_msg, max_lines=50)
        
        # 1. Khởi tạo Tools (Bao gồm read_file và search_code)
        selected_tool_names = ["search_code", "read_file"]
        ws_tools = WorkspaceTools(
            workspace_dir=workspace_dir,
            selected_tools=selected_tool_names
        )
        tools_map = {tool.name: tool for tool in ws_tools.get_tools()}
        openai_tools = WorkspaceTools.get_tool_definitions(
            workspace_dir=workspace_dir,
            selected_tools=selected_tool_names
        )

        # =====================================================================
        # PHA 1: ĐIỀU TRA HIỆN TRƯỜNG MÃ NGUỒN (CHỈ DÙNG TOOLS - THU THẬP BẰNG CHỨNG KHÁCH QUAN)
        # =====================================================================
        investigate_prompt = f"""Bạn là Kỹ thuật viên Giám định Hiện trường Mã nguồn (Forensic Code Investigator).
Nhiệm vụ DUY NHẤT: Thu thập BẰNG CHỨNG MÃ NGUỒN THỰC TẾ (FACTS / CODE SNIPPETS) tại các vị trí xảy ra lỗi để chuyển giao cho Thẩm phán (Verdict).
TUYỆT ĐỐI KHÔNG ĐƯA RA NHẬN ĐỊNH CHỦ QUAN, KHÔNG TỰ QUY KẾT TRÁCH NHIỆM CHO BẤT KỲ AGENT NÀO (Planner/Coder/Tester).

### DỮ LIỆU ĐẦU VÀO:
- Mục tiêu bài toán: {task_goal}
- Ngôn ngữ dự án: {plan.target_language}
- Kiến trúc: {plan.architecture_pattern}
- Danh sách tệp dự án: {[f.filepath for f in plan.files]}
- Log lỗi Sandbox:
{clean_error_msg if clean_error_msg else "Không có log lỗi."}

### CHIẾN LƯỢC ĐIỀU TRA BẰNG CHỨNG (TỐI ĐA 2-3 BƯỚC):
1. **Bước 1 - Khám nghiệm điểm lỗi trực tiếp (`read_file`):**
   - Nếu Log lỗi Sandbox nêu rõ tệp và dòng cụ thể (ví dụ: `<đường_dẫn_tệp>:<số_dòng>: error...`), BẮT BUỘC dùng ngay `read_file` để kiểm tra tệp đó trước.
   - Chỉ dùng `search_code` khi trong log xuất hiện tên symbol/hàm/class nhưng bạn CHƯA BIẾT nó được định nghĩa ở tệp nào trong dự án.
2. **Bước 2 - Kiểm tra điểm đối ứng / Hợp đồng (`read_file`):**
   - Nếu tệp bị lỗi đang gọi một symbol/class/hàm từ tệp khác nhưng bị báo lỗi chưa tìm thấy hoặc không tương thích, hãy dùng `read_file` đọc tệp chứa định nghĩa của symbol đó để xác minh:
     + Khai báo thực tế (prototype, class, hàm, struct, export/import).
     + Kiểu dữ liệu, tên symbol, chữ ký hàm thực tế có khớp với nơi gọi hay không.
3. **Bước 3 - Kết thúc và Xuất bằng chứng khách quan (`<evidence>`):**
   - Ngay sau khi đã đọc được nơi phát sinh lỗi và nơi định nghĩa đối ứng, DỪNG GỌI TOOL NGAY LẬP TỨC.
   - Xuất khối bằng chứng theo định dạng chuẩn:
     <evidence>
     - Điểm phát sinh lỗi: [Đường dẫn tệp, số dòng và đoạn code ngắn thực tế]
     - Điểm đối ứng/định nghĩa: [Đường dẫn tệp định nghĩa và đoạn code ngắn thực tế]
     - Dữ kiện thực tế ghi nhận: [Liệt kê các sự thật khách quan quan sát được từ code, không suy đoán, không phán xét]
     </evidence>
     ĐÃ ĐỦ BẰNG CHỨNG

<constrain>
- TIÊU CHÍ HÀNG ĐẦU: Thu thập nhanh, đúng trọng tâm. Chỉ đọc tối đa 2-3 tệp liên quan trực tiếp đến lỗi.
- KHÔNG đọc lan man sang các tệp không xuất hiện trong log lỗi hoặc không liên quan đến symbol lỗi.
- KHÔNG ĐƯỢC PHÁN XÉT: Không viết các câu nhận định như "Lỗi do Planner", "Coder làm sai", "Tester sai". Quyền phán quyết 100% thuộc về Thẩm phán ở pha sau.
</constrain>
"""

        initial_user_msg = (
            f"Bắt đầu thu thập chứng cứ cho log lỗi sau:\n{clean_error_msg}\n\n"
            f"Hãy bắt đầu bằng cách dùng tool `read_file` để đọc ngay tệp bị báo lỗi đầu tiên trong log lỗi (hoặc `search_code` nếu chưa rõ vị trí định nghĩa symbol lỗi)."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": investigate_prompt},
            {"role": "user", "content": initial_user_msg}
        ]

        investigation_notes = []
        latest_evidence = ""
        
        # Theo dõi tập hợp các tool call đã thực thi trong toàn bộ phiên hội thoại để chống gọi lặp lại
        executed_tool_calls: Set[Tuple[str, str]] = set()

        for iteration in range(self.max_tool_iterations):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=openai_tools if openai_tools else None,
                    tool_choice="auto" if openai_tools else None,
                    temperature=self.temperature
                )
            except Exception as e:
                print(f"⚠️ [Reviewer] Lỗi gọi API ở pha điều tra: {e}")
                break

            response_msg = response.choices[0].message
            tool_calls = getattr(response_msg, "tool_calls", None)
            content = response_msg.content or ""

            print(f"\n🔍 [Reviewer Debug - Iteration {iteration}]")
            print(f"   - Tool Calls tồn tại: {bool(tool_calls)}")
            print(f"   - Raw Content trả về:\n{content if content else '[KHÔNG CÓ TEXT CONTENT]'}")
            print("-" * 60)

            # Trích xuất thẻ evidence nếu có
            evidence_match = re.search(r"<evidence>(.*?)</evidence>", content, re.DOTALL | re.IGNORECASE)
            if evidence_match:
                latest_evidence = evidence_match.group(1).strip()
            elif "<evidence>" in content:
                latest_evidence = content.split("<evidence>", 1)[1].strip()

            has_searched = any(func == "search_code" for func, _ in executed_tool_calls)
            has_read = any(func == "read_file" for func, _ in executed_tool_calls)
            is_done_signaled = any(phrase in content.upper() for phrase in ["ĐÃ ĐỦ", "ĐÃ ĐỦ BẰNG CHỨNG", "ĐÃ ĐỦ THÔNG TIN"])

            # Nếu model đã phát tín hiệu kết thúc sau khi đã đọc ít nhất 1 file -> Dừng ngay
            if is_done_signaled and has_read:
                print(f"✅ [Reviewer] Phát hiện tín hiệu dừng ('ĐÃ ĐỦ BẰNG CHỨNG') sau khi đã kiểm tra thực địa.")
                break

            # Bắt trường hợp tool_calls native
            if tool_calls:
                messages.append(response_msg.model_dump() if hasattr(response_msg, "model_dump") else {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        } for tc in tool_calls
                    ]
                })

                for tc in tool_calls:
                    call_id = tc.id
                    func_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                    except Exception:
                        args = tc.function.arguments

                    call_signature = (func_name, self._normalize_tool_args(args))

                    # Kiểm tra xem tool và tham số này đã từng được gọi trong phiên hội thoại chưa
                    if call_signature in executed_tool_calls:
                        print(f"⚠️ [Reviewer] Phát hiện gọi lặp tool/tham số đã từng gọi trong phiên: {func_name}({args}). Hủy thực thi.")
                        tool_output = "Lỗi: Bạn đã từng gọi tool này với cùng tham số trước đó. Hãy xuất khối `<evidence>...</evidence> ĐÃ ĐỦ BẰNG CHỨNG` để kết thúc điều tra."
                    else:
                        executed_tool_calls.add(call_signature)
                        tool_output = self._execute_tool(tools_map, func_name, args)
                        print(f"🛠️ [Reviewer Tool] {func_name}({args}) -> Kích thước: {len(tool_output)} ký tự")
                        investigation_notes.append(f"File/Tool {func_name}({args}):\n{tool_output}\n")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": str(tool_output)
                    })

                updated_has_searched = any(func == "search_code" for func, _ in executed_tool_calls)
                updated_has_read = any(func == "read_file" for func, _ in executed_tool_calls)

                if updated_has_searched and not updated_has_read:
                    messages.append({
                        "role": "user",
                        "content": "Bạn đã hoàn thành `search_code`. Hãy dùng `read_file` để đọc trực tiếp tệp phát sinh lỗi hoặc tệp định nghĩa symbol liên quan."
                    })
                elif updated_has_read:
                    messages.append({
                        "role": "user",
                        "content": (
                            "Bạn đã có mã nguồn thực tế. Nếu đã đủ dữ kiện để đối chiếu nơi xảy ra lỗi và nơi định nghĩa liên quan, "
                            "hãy xuất ngay khối `<evidence>...</evidence> ĐÃ ĐỦ BẰNG CHỨNG` và KHÔNG gọi thêm tool nào. "
                            "Nếu còn thiếu tệp đối ứng quan trọng, hãy gọi duy nhất 1 lần `read_file` cho tệp đó."
                        )
                    })
                continue

            # Bắt trường hợp model in text tool calls (Bắt danh sách nhiều tool calls liên tiếp)
            text_tools = self._detect_text_tool_calls(content, tools_map)
            if text_tools:
                messages.append({"role": "assistant", "content": content})
                batch_results = []

                for func_name, args in text_tools:
                    call_signature = (func_name, self._normalize_tool_args(args))

                    if call_signature in executed_tool_calls:
                        print(f"⚠️ [Reviewer] Phát hiện text-tool gọi lặp lại: {call_signature}. Hủy thực thi.")
                        batch_results.append(f"Tool {func_name}({args}): Lỗi gọi lặp lại, đã từng thực thi. Hãy dừng gọi tool và xuất `<evidence>...</evidence> ĐÃ ĐỦ BẰNG CHỨNG`.")
                        continue

                    executed_tool_calls.add(call_signature)
                    tool_output = self._execute_tool(tools_map, func_name, args)
                    print(f"🛠️ [Reviewer Text-Tool] {func_name}({args}) -> Kích thước: {len(tool_output)} ký tự")
                    investigation_notes.append(f"File/Tool {func_name}({args}):\n{tool_output}\n")
                    batch_results.append(f"[TOOL RESULT for {func_name}({args})]:\n{tool_output}\n")

                if batch_results:
                    updated_has_searched = any(func == "search_code" for func, _ in executed_tool_calls)
                    updated_has_read = any(func == "read_file" for func, _ in executed_tool_calls)

                    next_instruction = "\n".join(batch_results) + "\n\n"
                    if updated_has_searched and not updated_has_read:
                        next_instruction += (
                            "Bạn đã có kết quả tìm kiếm. Tiếp theo, hãy dùng `read_file` để đọc trực tiếp "
                            "mã nguồn tại tệp phát sinh lỗi hoặc tệp định nghĩa liên quan."
                        )
                    else:
                        next_instruction += (
                            "Bạn đã có mã nguồn thực tế từ công cụ. "
                            "Nếu đã đủ dữ kiện để đối chiếu nơi xảy ra lỗi và nơi định nghĩa liên quan, "
                            "hãy xuất ngay khối `<evidence>...</evidence> ĐÃ ĐỦ BẰNG CHỨNG` và KHÔNG gọi thêm tool nào. "
                            "Nếu còn thiếu tệp đối ứng quan trọng, hãy gọi duy nhất 1 lần `read_file` cho tệp đó."
                        )

                    messages.append({
                        "role": "user",
                        "content": next_instruction
                    })
                continue

            # Hoàn tất quá trình điều tra khi không còn tool nào cần gọi
            print(f"✅ [Reviewer] Quá trình thu thập mã nguồn hoàn tất.")
            break

        existing_files_summary = "\n".join([
            f"- `{filepath}` ({len(content)} characters)" 
            for filepath, content in files_dict.items()
        ])
        code_overview = ""
        for filepath, content in files_dict.items():
            code_overview += f"\n--- FILE: `{filepath}` ---\n```{plan.target_language}\n{content}\n```\n"

        # =====================================================================
        # PHA 2: RA PHÁN QUYẾT & XUẤT JSON (KHÔNG DÙNG TOOLS)
        # =====================================================================
        evidence_sections = []
        if latest_evidence:
            evidence_sections.append(
                f"### [HỒ SƠ BẰNG CHỨNG HIỆN TRƯỜNG TỪ ĐIỀU TRA VIÊN (OBJECTIVE EVIDENCE)]:\n{latest_evidence}"
            )

        if investigation_notes:
            evidence_sections.append(
                f"### [MÃ NGUỒN CÁC TỆP LIÊN QUAN ĐÃ THU THẬP TỪ TOOLS]:\n" + "\n---\n".join(investigation_notes)
            )

        if evidence_sections:
            gathered_context = "\n\n".join(evidence_sections)
        else:
            print("⚠️ [Reviewer] Pha 1 không thu thập được tool note. Fallback nạp toàn bộ code_overview.")
            gathered_context = code_overview

        verdict_prompt = f"""BẠN LÀ THẨM PHÁN TỐI CAO (CODE AUDITOR).
Dưới đây là hồ sơ chứng cứ do điều tra viên thu thập từ hiện trường mã nguồn. Hãy đối chiếu khách quan với Yêu cầu bài toán gốc và Plan để đưa ra phán quyết cuối cùng:

### YÊU CẦU BÀI TOÁN GỐC (SPECIFICATION - CHÂN LÝ TỐI CAO):
{task_goal}
<context>
### [PLAN HIỆN TẠI (PLANNER)]:
Kiến trúc: {plan.architecture_pattern}
CHÚ Ý: TẤT CẢ CÁC TỆP DƯỚI ĐÂY ĐỀU ĐÃ ĐƯỢC TẠO RA VÀ ĐANG TỒN TẠI TRONG DỰ ÁN:
{existing_files_summary}

### LOG LỖI SANDBOX:
{error_msg}

<testcase - testharness>
{test_cases}
</testcase - testharness>

{gathered_context}

### QUY TRÌNH THẨM ĐỊNH VÀ NGUYÊN TẮC PHÂN ĐỊNH TRÁCH NHIỆM:
Danh sách file trách nhiệm sửa lỗi:
- Các file test_harness.py, test_harness.java, test_harness.c --> Thuộc về Tester
- Tất cả các file còn lại trong dự án --> Coder và Planner
</context>
<thought>
BƯỚC 1: Dựa vào log lỗi và hồ sơ chứng cứ xác định nguyên nhân chính

BƯỚC 2: CÂY QUYẾT ĐỊNH PHÂN ĐỊNH TRÁCH NHIỆM (CHỌN DUY NHẤT 1 TARGET):

1. **LỖI BIÊN DỊCH / CÚ PHÁP TẠI TỆP MÃ NGUỒN DỰ ÁN (LOẠI TRỪ TESTER):**
   - Nếu tệp bị lỗi trong log là tệp mã nguồn dự án của Coder/Planner (ví dụ: file .c, .h, .py, .java của dự án bị lỗi cú pháp, undefined symbol, thiếu header/import):
     -> NGUYÊN TẮC CỐT LÕI: Khi mã nguồn dự án không biên dịch được. Do đó lỗi 100% thuộc về CODER hoặc PLANNER, NGHIÊM CẤM ĐỔ LỖI CHO TESTER!
   - Phân định giữa PLANNER và CODER (Căn cứ vào plan và code):
     + **PLANNER (GLOBAL)**: Plan thiếu, sai, lệch , class, method, interface, dependancies giữa các file trong plan. 
     + **CODER (LOCAL)**: Plan đúng, có đề cập nhưng Coder không triển khai đúng, thiếu những gì plan đề cập, sai cú pháp, sai logic thân hàm.

2. LỖI BIÊN DỊCH / KHÔNG TÌM THẤY KÝ HIỆU TẠI TỆP KIỂM THỬ (TEST HARNESS)(LOẠI TRỪ PLANNER) 
   - Áp dụng khi log lỗi biên dịch/import chỉ ra vị trí đứt gãy xuất hiện, nằm trong file TestHarness (ví dụ: `TestHarness.java:8: error: cannot find symbol`, `testharness.c...`, `testharness.py...`)::
   BẮT BUỘC LẤY SPECIFICATION LÀM CHÂN LÝ ĐỂ ĐỐI CHIẾU:
   Trích xuất đúng Class / Method / Field / Signature đang bị báo lỗi trong TestHarness và so sánh với [1. YÊU CẦU BÀI TOÁN GỐC (SPECIFICATION)]:

   + TRƯỜNG HỢP 2.1 - CODER SAI (CODER / LOCAL):
     Nếu Class / Method / Signature /Interface mà TestHarness gọi CÓ ĐƯỢC YÊU CẦU TRONG SPECIFICATION, nhưng Coder không khai báo, đặt sai tên, truyền sai tham số, hoặc chưa triển khai.
     -> PHÁN QUYẾT: CODER (LOCAL).
     -> Root cause: Coder vi phạm hợp đồng (Contract) đã được quy định trong Specification.

   + TRƯỜNG HỢP 2.2 - TESTER SAI (TESTER / TESTCASE):
     Nếu Class / Method / Signature /Interface mà TestHarness gọi KHÔNG XUẤT HIỆN TRONG SPECIFICATION (Tester tự bịa ra tên hàm/Class/Interface mới, truyền thêm tham số không có trong đề bài, hoặc import/include sai package, class, thư viện).
     -> PHÁN QUYẾT: TESTER (TESTCASE).
     -> Root cause: Tester tự ý thay đổi Hợp đồng API (Contract) khác với yêu cầu bài toán gốc.

3. **LỖI RUNTIME / ASSERTION FAILURE (MÃ CHẠY ĐƯỢC NHƯNG TEST THẤT BẠI):** (LOẠI TRỪ PLANNER)
   - Áp dụng khi mã nguồn và TestHarness đều biên dịch thành công, nhưng khi thực thi bị Exception hoặc Assert fail.
   - Đối chiếu với [1. YÊU CẦU BÀI TOÁN GỐC]:
     + Nếu Coder tính toán sai thuật toán hoặc không đáp ứng đúng yêu cầu đề bài -> Chọn **CODER (LOCAL)**.
     + Nếu Coder đã làm đúng yêu cầu đề bài nhưng Testcase, assertion của file test kiểm tra điều kiện vô lý hoặc sai giá trị kỳ vọng -> Chọn **TESTER (TESTCASE)**.

BƯỚC 3: HƯỚNG DẪN SỬA (instructions):
   - Phải nêu rõ: sửa file nào, dòng/hàm nào, thay bằng cú pháp gì.
   - Hướng dẫn phải sửa đúng Root Cause, không đưa ra lời khuyên chung chung.
</thought>
<output_format>
{{
"status": "REJECTED",
"target": "PLANNER" | "CODER" | "TESTER",
"error_category": "GLOBAL" | "LOCAL" | "TESTCASE",
"failed_files": ["chỉ các file chứa nguyên nhân gốc cần sửa, không gồm caller hoặc file chỉ được nhắc tới"],
"root_cause": "nguyên nhân đã xác minh và vị trí phát sinh thực sự; phân biệt với nơi lỗi được gọi hoặc phát hiện",
"instructions": "cách sửa tối thiểu, cụ thể, hợp lệ với code/API thực tế; nêu file và thay đổi cần thực hiện, không đưa ra hướng dẫn chung chung",
"audit_table": "tóm tắt đối chiếu"
}}
</output_format>
"""
        print(f"⚖️ [Reviewer] Đang tổng hợp phán quyết cuối cùng...")
        raw_resp = self.call_llm(verdict_prompt, format_json=True)
        print(f"DEBUG FINAL VERDICT JSON:\n{raw_resp}\n" + "="*50)

        # Parse kết quả JSON ra ReviewDecision
        json_obj = self.extract_json_object(raw_resp)
        if json_obj and "target" in json_obj:
            try:
                target_str = str(json_obj.get("target", "UNKNOWN")).upper().strip()
                if "PLANNER" in target_str:
                    target_enum = ReviewTarget.PLANNER
                    cat = "GLOBAL"
                elif "TESTER" in target_str:
                    target_enum = ReviewTarget.TESTER
                    cat = "TESTCASE"
                elif "PASSED" in target_str:
                    target_enum = ReviewTarget.PASSED
                    cat = "NONE"
                else:
                    target_enum = ReviewTarget.CODER
                    cat = "LOCAL"

                raw_audit = json_obj.get("audit_table", "")
                audit_table_val = json.dumps(raw_audit, ensure_ascii=False, indent=2) if isinstance(raw_audit, (dict, list)) else str(raw_audit or "")

                raw_failed_files = json_obj.get("failed_files")
                if raw_failed_files is None and json_obj.get("failed_file"):
                    raw_failed_files = [json_obj.get("failed_file")]

                failed_files_list: List[str] = []
                if isinstance(raw_failed_files, list):
                    failed_files_list = [str(f).strip().strip("`'\"") for f in raw_failed_files if f]
                elif isinstance(raw_failed_files, str):
                    failed_files_list = [f.strip().strip("`'\"") for f in raw_failed_files.split(",") if f.strip()]

                valid_failed_files = [f for f in failed_files_list if f in files_dict]

                decision_kwargs = {
                    "status": str(json_obj.get("status", "REJECTED")),
                    "target": target_enum,
                    "error_category": str(json_obj.get("error_category", cat)),
                    "root_cause": str(json_obj.get("root_cause", "Phát hiện lỗi khi thực thi sandbox.")),
                    "instructions": str(json_obj.get("instructions", "Vui lòng kiểm tra và sửa đổi theo log lỗi.")),
                    "audit_table": audit_table_val
                }

                schema_fields = getattr(ReviewDecision, "__fields__", {}) or getattr(ReviewDecision, "__annotations__", {})
                if "failed_files" in schema_fields:
                    decision_kwargs["failed_files"] = valid_failed_files
                if "failed_file" in schema_fields:
                    decision_kwargs["failed_file"] = valid_failed_files[0] if valid_failed_files else None

                decision = ReviewDecision(**decision_kwargs)
                setattr(decision, "failed_files", valid_failed_files)
                return decision

            except Exception as e:
                print(f"⚠️ [Reviewer] Lỗi parse sang ReviewDecision: {e}")

        return self._fallback_parse_decision(raw_resp, error_msg, files_dict)

    def _fallback_parse_decision(
        self,
        raw_resp: str,
        error_msg: str,
        files_dict: Dict[str, str]
    ) -> ReviewDecision:
        """Fallback khi LLM không trả về JSON hợp lệ."""
        print("⚠️ [Reviewer] Đang kích hoạt Fallback Parser...")
        upper_resp = raw_resp.upper()
        
        target = ReviewTarget.CODER
        category = "LOCAL"
        if "PLANNER" in upper_resp:
            target = ReviewTarget.PLANNER
            category = "GLOBAL"
        elif "TESTER" in upper_resp:
            target = ReviewTarget.TESTER
            category = "TESTCASE"

        # Quét tệp lỗi từ files_dict
        detected_files = [f for f in files_dict.keys() if f in raw_resp or os.path.basename(f) in raw_resp]

        return ReviewDecision(
            status="REJECTED",
            target=target,
            error_category=category,
            failed_files=detected_files,
            root_cause=f"Không thể phân tích phản hồi chi tiết từ LLM. Lỗi gốc: {error_msg[:200]}...",
            instructions="Vui lòng đọc lại log lỗi Sandbox và khắc phục sự cố.",
            audit_table=""
        )
