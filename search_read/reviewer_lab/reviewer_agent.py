"""
multi_agent_system.agents.reviewer_agent
======================================
Agent Reviewer: Tiếp nhận task, plan, code đa tệp, testcase, cây thư mục và log lỗi Sandbox.
Thẩm định nguyên nhân cốt lõi và phân định chính xác:
- PLANNER: Lỗi Global (mâu thuẫn giữa các file, sai import, lệch interface)
- CODER: Lỗi Local (cú pháp nội bộ trong 1 file, lỗi logic cài đặt thân hàm)
- TESTER: Lỗi Testcase (assert sai kỳ vọng, testcase vi phạm yêu cầu bài toán)
"""

import json
import os
import re
from typing import Dict, Optional, Any, List, Set, Tuple
from types import SimpleNamespace
from openai import OpenAI
from typer import prompt
from multi_agent_system.schemas import MultiFilePlan, ReviewDecision, ReviewTarget
from multi_agent_system import config
from multi_agent_system.tools.workspace_tools import WorkspaceTools


class ReviewerAgent:
    max_tool_iterations: int = 10
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tool_iterations: int = 10
    ):
        self.model_name = model_name or config.REVIEWER_MODEL
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.temperature = 0.1
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
    def _detect_text_tool_call(self, text: str, tools_map: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Bắt trường hợp LLM sinh text JSON gọi hàm thay vì gửi qua API tool_calls.
        Ví dụ: {"name": "read_file", "arguments": {"file_path": "..."}}
        """
        if not text:
            return None
            
        obj = self.extract_json_object(text)
        if not obj or not isinstance(obj, dict):
            return None

        # Trường hợp 1: {"name": "read_file", "arguments": {...}}
        func_name = obj.get("name") or obj.get("function") or obj.get("tool")
        func_args = obj.get("arguments") or obj.get("parameters") or obj.get("args")

        if func_name and func_name in tools_map:
            if isinstance(func_args, str):
                try:
                    func_args = json.loads(func_args)
                except Exception:
                    pass
            return str(func_name), func_args if isinstance(func_args, dict) else {}

        # Trường hợp 2: {"action": "read_file", "action_input": {...}}
        action = obj.get("action")
        if action and action in tools_map:
            action_input = obj.get("action_input", {})
            return str(action), action_input if isinstance(action_input, dict) else {}

        return None
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
    def review(
        self,
        task_goal: str,
        plan: MultiFilePlan,
        files_dict: Dict[str, str],
        test_cases: str,
        error_msg: str,
        workspace_dir: str
    ) -> ReviewDecision:
        # 1. Khởi tạo Tools
        ws_tools = WorkspaceTools(
            workspace_dir=workspace_dir,
            selected_tools=["read_file", "list_directory", "file_search"]
        )
        tools_map = {tool.name: tool for tool in ws_tools.get_tools()}
        openai_tools = WorkspaceTools.get_tool_definitions(
            workspace_dir=workspace_dir,
            selected_tools=["read_file", "list_directory", "file_search"]
        )

        # =====================================================================
        # PHA 1: ĐIỀU TRA MÃ NGUỒN (CHỈ DÙNG TOOLS)
        # =====================================================================
        investigate_prompt = f"""Bạn là một Chuyên gia Kỹ thuật Phần mềm và Chuyên viên Phân tích Mã nguồn cấp cao.
Nhiệm vụ của bạn là trả lời các câu hỏi kỹ thuật về mã nguồn trong workspace một cách chính xác, sâu sắc và có căn cứ rõ ràng.

### DỮ LIỆU ĐẦU VÀO:
- Mục tiêu bài toán: {task_goal}
- Cấu trúc hệ thống: {plan.architecture_pattern}
- Danh sách tệp: {[f.filepath for f in plan.files]}
### NHIỆM VỤ:
- Hãy tìm và đọc file sau đó trả lời log lỗi này do các file nào gây ra trong workspace:
{error_msg if error_msg else "Chưa có log lỗi. Hãy kiểm tra các file chính theo plan."}

Bạn được cung cấp 3 công cụ quan trọng:
1. `search_grep`: Tìm kiếm vị trí khai báo hàm, class, từ khóa, interface, v.v. trong mã nguồn.
2. `read_file`: Đọc mã nguồn chi tiết của một file theo số dòng.

QUY TẮC BẮT BUỘC KHI LÀM VIỆC:
- BƯỚC 1: LUÔN bắt đầu bằng việc dùng `search_grep` để tìm vị trí xuất hiện của từ khóa, class, method.
  * TUYỆT ĐỐI KHÔNG gọi `read_file` ở Bước 1 khi chưa có kết quả `search_grep`.
  * TUYỆT ĐỐI KHÔNG tự bịa hoặc suy đoán đường dẫn file (ví dụ: KHÔNG đoán các thư mục ảo như `com/example/...`).
- BƯỚC 2 TRỞ ĐI: Dựa vào kết quả `search_grep` trả về, nhìn chính xác đường dẫn file thực tế trong workspace (ví dụ: `java/src/Main.java`, `java/src/engine/EventDispatcher.java`) và dùng `read_file` để đọc nội dung.
- NẾU GẶP LỖI FILE KHÔNG TỒN TẠI: Dừng lại ngay, xem lại danh sách file mà `search_grep` đã tìm thấy để lấy đúng file.
- KHI ĐÃ ĐỦ THÔNG TIN: hãy trả lời "ĐÃ ĐỦ THÔNG TIN" và không gọi thêm tool nữa.
"""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": investigate_prompt},
            {"role": "user", "content": "Hãy phân tích log lỗi và dùng tool đọc các file code bị nghi vấn."}
        ]

        investigation_notes = []

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

                    tool_output = self._execute_tool(tools_map, func_name, args)
                    print(f"🛠️ [Reviewer Tool] {func_name}({args}) -> Kích thước: {len(tool_output)} ký tự")
                    investigation_notes.append(f"File/Tool {func_name}({args}):\n{tool_output}\n")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": str(tool_output)
                    })
                continue

            # Bắt trường hợp model in text tool call (dự phòng)
            text_tool = self._detect_text_tool_call(content, tools_map)
            if text_tool:
                func_name, args = text_tool
                tool_output = self._execute_tool(tools_map, func_name, args)
                print(f"🛠️ [Reviewer Text-Tool] {func_name}({args}) -> Kích thước: {len(tool_output)} ký tự")
                investigation_notes.append(f"File/Tool {func_name}({args}):\n{tool_output}\n")

                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"[TOOL RESULT]:\n{tool_output}\n\nHãy tiếp tục dùng tool đọc thêm nếu cần, hoặc trả lời 'ĐÃ ĐỦ THÔNG TIN'."
                })
                continue

            # Nếu model không gọi tool nữa hoặc báo đã đủ thông tin
            print(f"✅ [Reviewer] Quá trình thu thập mã nguồn hoàn tất.")
            break

        # =====================================================================
        # PHA 2: RA PHÁN QUYẾT & XUẤT JSON (KHÔNG DÙNG TOOLS)
        # =====================================================================
        gathered_context = "\n---\n".join(investigation_notes) if investigation_notes else "Không có file nào được đọc thêm."

        verdict_prompt = f"""BẠN LÀ THẨM PHÁN TỐI CAO (CODE AUDITOR).
Dựa trên thông tin gốc và toàn bộ nội dung code thực tế vừa điều tra được, hãy đưa ra phán quyết cuối cùng.

### YÊU CẦU BÀI TOÁN GỐC:
{task_goal}

### [PLAN HIỆN TẠI (PLANNER)]:
Kiến trúc: {plan.architecture_pattern}
Các tệp: {[f.filepath for f in plan.files]}

### LOG LỖI SANDBOX:
{error_msg}

### KỊCH BẢN TEST:
{test_cases}

### NỘI DUNG CODE ĐÃ ĐIỀU TRA ĐƯỢC:
{gathered_context}


BƯỚC 1: ĐỀ XUẤT CÁCH SỬA CÓ THỂ THỰC THI:
1. Đối chiếu root cause với code hiện tại, API/signature thực tế, plan và specification trước khi đề xuất thay đổi.
2. Chỉ dẫn sửa phải cụ thể: nêu file cần sửa, lỗi cần xử lý và thay đổi tối thiểu đủ khắc phục root cause. Đảm bảo thay đổi phù hợp với ngôn ngữ và kiểu đối tượng thực tế.
3. Không đề xuất gọi method/field/import/constructor chưa tồn tại hoặc không phù hợp với kiểu đối tượng. Không đưa ra hướng dẫn chung chung, lặp lại chính dòng gây lỗi, hay chỉ thị không làm thay đổi nguyên nhân.
4. Trước khi trả kết quả, tự kiểm tra: nếu làm đúng instructions thì lỗi trong log có được loại bỏ không, và thay đổi có tạo lỗi mới hoặc vi phạm specification không? Nếu không thể xác minh, nêu giới hạn thay vì đoán.
5. Ưu tiên sửa file có khả năng giảm lỗi nhiều nhất và chỉ liệt kê file thực sự cần thay đổi. Nếu log có nhiều root cause độc lập, ghi rõ chúng và cách sửa tương ứng trong instructions, đồng thời chọn target cần xử lý ở vòng hiện tại.

BƯỚC 2: CÂY QUYẾT ĐỊNH PHÂN ĐỊNH TRÁCH NHIỆM (CHỌN DUY NHẤT 1 TARGET):

1. **LỖI BIÊN DỊCH / CÚ PHÁP TẠI TỆP MÃ NGUỒN DỰ ÁN (TUYỆT ĐỐI KHÔNG CHỌN TESTER):**
   - Nếu tệp bị lỗi trong log là tệp mã nguồn của Coder/Planner (ví dụ: `services/MovieService.java:8: error: cannot find symbol`, `data/MovieRepository.java`, `Main.java`):
     -> NGUYÊN TẮC CỐT LÕI: Khi mã nguồn dự án không biên dịch được. Do đó lỗi 100% thuộc về CODER hoặc PLANNER, NGHIÊM CẤM ĐỔ LỖI CHO TESTER!
   - Phân định giữa PLANNER và CODER (Căn cứ vào plan và code):
     + **PLANNER (GLOBAL)**: Plan thiếu, sai, lệch class, method, interface giữa các file trong plan. 
     + **CODER (LOCAL)**: Plan đúng, có đề cập nhưng Coder không triển khai đúng, thiếu những gì plan đề cập, sai cú pháp, sai logic thân hàm.

2. LỖI BIÊN DỊCH / KHÔNG TÌM THẤY KÝ HIỆU TẠI TỆP KIỂM THỬ (TEST HARNESS):
   (Áp dụng khi log lỗi biên dịch/import chỉ ra vị trí đứt gãy xuất hiện, nằm trong file TestHarness)

   👉 BẮT BUỘC LẤY SPECIFICATION LÀM CHÂN LÝ ĐỂ ĐỐI CHIẾU:
   Trích xuất đúng Class / Method / Field / Signature đang bị báo lỗi trong TestHarness và so sánh với [1. YÊU CẦU BÀI TOÁN GỐC (SPECIFICATION)]:

   + TRƯỜNG HỢP 2.1 - CODER SAI (CODER / LOCAL):
     Nếu Class / Method / Signature /Interface mà TestHarness gọi CÓ ĐƯỢC YÊU CẦU TRONG SPECIFICATION, nhưng Coder không khai báo, đặt sai tên, truyền sai tham số, hoặc chưa triển khai.
     -> PHÁN QUYẾT: CODER (LOCAL).
     -> Root cause: Coder vi phạm hợp đồng (Contract) đã được quy định trong Specification.

   + TRƯỜNG HỢP 2.2 - TESTER SAI (TESTER / TESTCASE):
     Nếu Class / Method / Signature /Interface mà TestHarness gọi KHÔNG XUẤT HIỆN TRONG SPECIFICATION (Tester tự bịa ra tên hàm/Class/Interface mới, truyền thêm tham số không có trong đề bài, hoặc import/include sai package, class, thư viện).
     -> PHÁN QUYẾT: TESTER (TESTCASE).
     -> Root cause: Tester tự ý thay đổi Hợp đồng API (Contract) khác với yêu cầu bài toán gốc.

3. **LỖI RUNTIME / ASSERTION FAILURE (MÃ CHẠY ĐƯỢC NHƯNG TEST THẤT BẠI):**
   - Áp dụng khi mã nguồn và TestHarness đều biên dịch thành công, nhưng khi thực thi bị Exception hoặc Assert fail.
   - Đối chiếu với [1. YÊU CẦU BÀI TOÁN GỐC]:
     + Nếu Coder tính toán sai thuật toán hoặc không đáp ứng đúng yêu cầu đề bài -> Chọn **CODER (LOCAL)**.
     + Nếu Coder đã làm đúng yêu cầu đề bài nhưng Testcase, assertion của file test kiểm tra điều kiện vô lý hoặc sai giá trị kỳ vọng -> Chọn **TESTER (TESTCASE)**.

HÃY XUẤT DUY NHẤT MỘT JSON OBJECT CÓ CẤU TRÚC SAU:
{{
"status": "REJECTED",
"target": "PLANNER" | "CODER" | "TESTER",
"error_category": "GLOBAL" | "LOCAL" | "TESTCASE",
"failed_files": ["chỉ các file chứa nguyên nhân gốc cần sửa, không gồm caller hoặc file chỉ được nhắc tới"],
"root_cause": "nguyên nhân đã xác minh và vị trí phát sinh thực sự; phân biệt với nơi lỗi được gọi hoặc phát hiện",
"instructions": "cách sửa tối thiểu, cụ thể, hợp lệ với code/API thực tế; nêu file và thay đổi cần thực hiện, không đưa ra hướng dẫn chung chung",
"audit_table": "tóm tắt đối chiếu"
}}
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