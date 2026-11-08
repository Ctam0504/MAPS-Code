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
from pathlib import Path
from .base_agent import BaseAgent
from ..schemas import LanguageType, MultiFilePlan, ReviewDecision, ReviewTarget
from .. import config
import re
from ..tools.workspace_tools import WorkspaceTools

class ReviewerAgent(BaseAgent):
    max_tool_iterations: int = 6

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tool_iterations: int = 6
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

    @staticmethod
    def _load_review_skill(target_language: str) -> Tuple[str, str, str, str]:
        language = LanguageType.from_str(target_language).value
        skills_dir = Path(__file__).resolve().parents[1] / "reviewer_skills"
        common_path = skills_dir / "common" / "review_protocol.md"
        language_path = skills_dir / language / "SKILL.md"

        try:
            common_rules = common_path.read_text(encoding="utf-8")
            skill_content = language_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Không thể nạp Reviewer skill cho ngôn ngữ '{language}': {exc}") from exc

        investigation_match = re.search(
            r"^## Phase 1: Investigation guidance\s*\n(.*?)(?=^## |\Z)",
            skill_content,
            re.MULTILINE | re.DOTALL
        )
        verdict_match = re.search(
            r"^## Phase 2: Verdict rules\s*\n(.*?)(?=^## |\Z)",
            skill_content,
            re.MULTILINE | re.DOTALL
        )
        if investigation_match is None or verdict_match is None:
            missing_sections = []
            if investigation_match is None:
                missing_sections.append("investigation")
            if verdict_match is None:
                missing_sections.append("verdict")
            raise ValueError(
                f"Reviewer skill '{language}' thiếu section bắt buộc: {', '.join(missing_sections)}."
            )

        return (
            language,
            common_rules.strip(),
            investigation_match.group(1).strip(),
            verdict_match.group(1).strip()
        )

    def review(
        self,
        task_goal: str,
        plan: MultiFilePlan,
        files_dict: Dict[str, str],
        test_cases: str,
        error_msg: str,
        workspace_dir: str
    ) -> ReviewDecision:
        language, common_skill, investigation_skill, verdict_skill = self._load_review_skill(
            plan.target_language
        )
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

        investigate_prompt = f"""Kiểm tra log sandbox và các phần mã nguồn liên quan. Làm theo hướng dẫn điều tra của ngôn ngữ, rồi trả về các vị trí lỗi cùng nội dung source/declaration cần để đối chiếu.

### Input
- Goal: {task_goal}
- Language: {language}
- Plan: {plan.architecture_pattern}
- Project files: {[f.filepath for f in plan.files]}
- Sandbox log:
{clean_error_msg if clean_error_msg else "No sandbox log."}
- Test harness/input:
```{language}
{test_cases}
```

### Investigation guidance
{common_skill}

{investigation_skill}

### Evidence output
Return an `<evidence>` block containing the reported diagnostic locations and messages, relevant source snippets, and related declarations/imports/build facts that you inspected. End with `ĐÃ ĐỦ BẰNG CHỨNG` when the relevant evidence is collected.
"""

        initial_user_msg = (
            f"Bắt đầu thu thập chứng cứ cho log lỗi sau:\n{clean_error_msg}\n\n"
            "Làm theo hướng dẫn điều tra của ngôn ngữ để kiểm tra log và các source liên quan."
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

            if is_done_signaled and has_read:
                print("✅ [Reviewer] Điều tra viên báo đã đủ bằng chứng; kết thúc điều tra.")
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
        plan_contract_summary = "\n".join(
            f"- `{spec.filepath}`: {spec.interface_summary or spec.purpose}; "
            f"dependencies={spec.dependencies}"
            for spec in plan.files
        )
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
        elif investigation_notes:
            evidence_sections.append(
                "### [MÃ NGUỒN LIÊN QUAN ĐÃ THU THẬP TỪ TOOLS "
                "(FALLBACK: KHÔNG CÓ KHỐI EVIDENCE)]:\n"
                + "\n---\n".join(investigation_notes)
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
Ngôn ngữ: {language}
### File contracts from the Planner:
{plan_contract_summary}
### Files currently existing in the project:
{existing_files_summary}
</context>

### LOG LỖI SANDBOX:
{clean_error_msg}
Phán quyết phải giải thích lỗi thất bại đầu tiên trong log này. Mọi kết luận và hướng sửa phải truy nguyên được về log, evidence, file list, plan hoặc testcase; không đưa ra API, symbol, module path hay đề xuất mới không có căn cứ. Dùng rule trong skill ngôn ngữ để phân tích và chọn target.

<testcase - testharness>
{test_cases}
</testcase - testharness>

{gathered_context}

### REVIEW SKILL — QUY TẮC PHÂN TÍCH CHO {language.upper()}:
Áp dụng các rule sau khi chúng phù hợp với log và bằng chứng thực tế. Đây là hướng dẫn phân tích,
không thay thế specification, plan, mã nguồn hoặc kết quả sandbox:
{verdict_skill}

### SHARED REVIEW PROTOCOL:
{common_skill}

### Decision requirements:
- Start from the first failure in the sandbox log. The stack trace's test frame is not itself proof that the test harness caused the failure.
- Explain the exact failing symbol/construct using the matching source evidence. When the evidence says a name is used but not imported, check its definition and the failing file's imports before deciding.
- Use only files and symbols present in the log, provided evidence, plan, source files, or test harness. Do not invent an unrelated exception, method, file, or sample implementation.
- `failed_files` must contain only existing project files that need modification. Do not put a test harness in this list unless it is actually the primary failing artifact and is handled as TESTER.
- Give a minimal correction that fixes the evidenced cause and preserves the existing plan/API. Do not offer speculative alternatives or generic instructions.
</context>
<output_format>
{{
"status": "REJECTED",
"target": "PLANNER" | "CODER" | "TESTER",
"error_category": "GLOBAL" | "LOCAL" | "TESTCASE",
"failed_files": ["exact existing project file paths that need changes"],
"root_cause": "the first evidenced failure, exact file/line/symbol, and why it fails",
"instructions": "minimal change supported by the evidence; preserve planned interfaces",
"audit_table": "evidence-to-conclusion mapping; mention secondary issues only when present in the log/evidence"
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
                target_str = str(json_obj.get("target", "CODER")).upper().strip()
                if "PLANNER" in target_str:
                    target_enum = ReviewTarget.PLANNER
                    cat = "GLOBAL"
                elif "TESTER" in target_str:
                    target_enum = ReviewTarget.TESTER
                    cat = "TESTCASE"
                elif target_str == "PASSED":
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

                response_category = str(json_obj.get("error_category", cat)).upper().strip()
                if response_category not in {"GLOBAL", "LOCAL", "TESTCASE", "NONE"}:
                    response_category = cat

                decision_kwargs = {
                    "status": str(json_obj.get("status", "REJECTED")),
                    "target": target_enum,
                    "error_category": response_category,
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

        fallback_decision = self._fallback_parse_decision("", error_msg, files_dict)
        return fallback_decision

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
        detected_files = [
            f for f in files_dict.keys()
            if f in raw_resp
            or os.path.basename(f) in raw_resp
            or f in error_msg
            or os.path.basename(f) in error_msg
        ]

        return ReviewDecision(
            status="REJECTED",
            target=target,
            error_category=category,
            failed_files=detected_files,
            root_cause=f"Không thể phân tích phản hồi chi tiết từ LLM. Lỗi gốc: {error_msg[:200]}...",
            instructions="Vui lòng đọc lại log lỗi Sandbox và khắc phục sự cố.",
            audit_table=""
        )
