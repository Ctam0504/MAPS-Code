#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Qwen2.5-Coder-7B tích hợp tools:
- read_file(path, line_range): Đọc nội dung file theo đường dẫn và khoảng dòng
- search_grep(query, path): Tìm kiếm từ khóa/hàm trong toàn bộ workspace

Dùng để tự động trả lời các câu hỏi về mã nguồn trong thư mục được chỉ định.
"""

import os
import re
import sys
import json
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime
import argparse

# Thiết lập encoding UTF-8 cho Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from openai import OpenAI
except ImportError:
    print("[Error] Thư viện 'openai' chưa được cài đặt. Vui lòng chạy: pip install openai")
    sys.exit(1)


# ==========================================
# 1. CÔNG CỤ XỬ LÝ WORKSPACE (TOOLS)
# ==========================================

class WorkspaceTools:
    """Tập hợp các công cụ thao tác với workspace."""

    # Các thư mục hoặc file nên bỏ qua khi tìm kiếm
    IGNORE_DIRS = {
        ".git", ".svn", ".hg", "__pycache__", "venv", ".venv", "env",
        ".env", "node_modules", "target", "build", "dist", ".idea",
        ".vscode", ".gemini", ".next", ".nuxt", "bin", "obj"
    }
    
    IGNORE_EXTENSIONS = {
        ".exe", ".dll", ".so", ".dylib", ".bin", ".obj", ".o", ".a",
        ".lib", ".pyc", ".pyd", ".png", ".jpg", ".jpeg", ".gif",
        ".pdf", ".zip", ".tar", ".gz", ".7z", ".mp4", ".mp3"
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir).resolve()
        if not self.workspace_dir.exists():
            raise FileNotFoundError(f"Thư mục workspace không tồn tại: {self.workspace_dir}")

    def _resolve_path(self, file_path: str) -> Path:
        """Chuẩn hóa đường dẫn tương đối hoặc tuyệt đối."""
        p = Path(file_path)
        if not p.is_absolute():
            p = (self.workspace_dir / p).resolve()
        else:
            p = p.resolve()
        return p

    def read_file(self, path: str, line_range: Optional[Union[List[int], Tuple[int, int], str]] = None) -> str:
        """
        Đọc nội dung file theo đường dẫn và khoảng dòng (1-indexed).
        
        Args:
            path: Đường dẫn tới file (tương đối theo workspace hoặc tuyệt đối).
            line_range: Khoảng dòng muốn đọc. 
                        Ví dụ: [1, 50], (1, 50), "1-50", hoặc số nguyên.
                        Nếu None: đọc toàn bộ (tối đa 300 dòng đầu để tránh tràn context).
        """
        target = self._resolve_path(path)
        auto_healed_notice = ""
        
        if not target.exists() or not target.is_file():
            # Thử tự động tìm kiếm file trong workspace nếu model đoán sai cấu trúc package (Smart Auto-Healing)
            target_name = Path(path).name.lower()
            matched_candidates = []
            stem_candidates = []
            stem = Path(path).stem.lower()

            for root, dirs, files in os.walk(self.workspace_dir):
                dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith(".")]
                for f in files:
                    if f.lower() == target_name:
                        matched_candidates.append(Path(root) / f)
                    elif stem and stem in f.lower():
                        stem_candidates.append(Path(root) / f)

            if matched_candidates:
                chosen = matched_candidates[0]
                rel_old = path.replace("\\", "/")
                rel_new = os.path.relpath(chosen, self.workspace_dir).replace("\\", "/")
                auto_healed_notice = f"[Lưu ý: Không tìm thấy '{rel_old}', hệ thống tự động tìm thấy và đọc file tương ứng: '{rel_new}']\n"
                target = chosen
            elif stem_candidates:
                chosen = stem_candidates[0]
                rel_old = path.replace("\\", "/")
                rel_new = os.path.relpath(chosen, self.workspace_dir).replace("\\", "/")
                auto_healed_notice = f"[Lưu ý: Không tìm thấy '{rel_old}', hệ thống gợi ý và đọc file khớp nhất: '{rel_new}']\n"
                target = chosen
            else:
                return f"[Error] File không tồn tại: {path} (Đường dẫn giải quyết: {target}). Vui lòng dùng kết quả từ search_grep để lấy đúng đường dẫn file thực tế."

        if not target.is_file():
            return f"[Error] Đường dẫn không phải là file: {path}"

        # Đọc nội dung file với xử lý encoding linh hoạt
        content = None
        for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                with open(target, "r", encoding=enc) as f:
                    content = f.readlines()
                break
            except (UnicodeDecodeError, Exception):
                continue

        if content is None:
            return f"[Error] Không thể giải mã nội dung file: {path}"

        total_lines = len(content)
        if total_lines == 0:
            return f"[File rỗng: {path}]"

        start_line = 1
        end_line = total_lines

        # Phân tích cú pháp line_range
        if line_range is not None:
            try:
                if isinstance(line_range, (list, tuple)) and len(line_range) >= 2:
                    start_line = int(line_range[0])
                    end_line = int(line_range[1])
                elif isinstance(line_range, (list, tuple)) and len(line_range) == 1:
                    start_line = int(line_range[0])
                    end_line = total_lines
                elif isinstance(line_range, str):
                    clean_str = line_range.strip().strip("[]()")
                    if "-" in clean_str:
                        parts = clean_str.split("-")
                        start_line = int(parts[0].strip())
                        end_line = int(parts[1].strip())
                    elif "," in clean_str:
                        parts = clean_str.split(",")
                        start_line = int(parts[0].strip())
                        end_line = int(parts[1].strip())
                    elif clean_str.isdigit():
                        start_line = int(clean_str)
                        end_line = min(start_line + 50, total_lines)
                elif isinstance(line_range, int):
                    start_line = line_range
                    end_line = min(start_line + 50, total_lines)
            except Exception as e:
                return f"[Warning: Lỗi định dạng line_range '{line_range}', sẽ đọc 1-100. Chi tiết: {e}]"

        # Ràng buộc chỉ số hợp lệ (1-indexed)
        start_line = max(1, start_line)
        end_line = min(total_lines, end_line)

        if start_line > total_lines:
            return f"[Error] start_line ({start_line}) vượt quá tổng số dòng của file ({total_lines})."
        if start_line > end_line:
            start_line, end_line = end_line, start_line

        # Cắt dòng và thêm số dòng
        selected_lines = content[start_line - 1 : end_line]
        rel_path = os.path.relpath(target, self.workspace_dir).replace("\\", "/")

        output = []
        if auto_healed_notice:
            output.append(auto_healed_notice.strip())
        output.append(f"=== File: {rel_path} (Dòng {start_line} - {end_line} / Tổng {total_lines} dòng) ===")
        for idx, line in enumerate(selected_lines, start=start_line):
            output.append(f"{idx:4d} | {line.rstrip()}")

        return "\n".join(output)

    def search_grep(self, query: str, path: Optional[str] = None) -> str:
        """
        Tìm kiếm từ khóa/hàm/biểu thức chính quy trong toàn bộ workspace hoặc thư mục con.
        
        Args:
            query: Từ khóa hoặc biểu thức regex cần tìm.
            path: Thư mục hoặc file con cụ thể để giới hạn phạm vi tìm kiếm (tùy chọn).
        """
        if not query or not query.strip():
            return "[Error] Query tìm kiếm không được để trống."

        search_root = self.workspace_dir
        if path:
            search_root = self._resolve_path(path)
            if not search_root.exists():
                return f"[Error] Đường dẫn tìm kiếm không tồn tại: {path}"

        matches = []
        max_results = 40  # Tránh tràn context window
        case_insensitive = True

        try:
            pattern = re.compile(query, re.IGNORECASE if case_insensitive else 0)
        except re.error:
            # Nếu query không phải regex hợp lệ, coi như chuỗi thông thường
            pattern = re.compile(re.escape(query), re.IGNORECASE if case_insensitive else 0)

        # Duyệt cây thư mục
        if search_root.is_file():
            files_to_scan = [search_root]
        else:
            files_to_scan = []
            for root, dirs, files in os.walk(search_root):
                # Bỏ qua các thư mục không cần thiết
                dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith(".")]
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in self.IGNORE_EXTENSIONS:
                        continue
                    files_to_scan.append(Path(root) / f)

        # Quét các file
        for file_path in files_to_scan:
            try:
                # Bỏ qua file quá lớn (> 2MB)
                if file_path.stat().st_size > 2 * 1024 * 1024:
                    continue

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        if pattern.search(line):
                            rel_p = os.path.relpath(file_path, self.workspace_dir).replace("\\", "/")
                            cleaned_line = line.strip()
                            if len(cleaned_line) > 180:
                                cleaned_line = cleaned_line[:177] + "..."
                            matches.append(f"{rel_p}:{line_num}: {cleaned_line}")
                            if len(matches) >= max_results:
                                break
            except Exception:
                continue

            if len(matches) >= max_results:
                break

        if not matches:
            return f"Không tìm thấy kết quả nào khớp với '{query}' trong workspace."

        summary = f"Tìm thấy {len(matches)} kết quả cho '{query}'"
        if len(matches) >= max_results:
            summary += f" (Đã giới hạn tối đa {max_results} kết quả đầu tiên):"
        else:
            summary += ":"

        return summary + "\n" + "\n".join(matches)

    @classmethod
    def get_tool_definitions(cls) -> List[Dict[str, Any]]:
        """Khai báo function calling schema theo chuẩn OpenAI / Ollama."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_grep",
                    "description": "Tìm kiếm từ khóa, tên hàm, class, hoặc biến trong toàn bộ workspace hoặc thư mục con.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Từ khóa hoặc tên hàm/class cần tìm kiếm."
                            },
                            "path": {
                                "type": "string",
                                "description": "Đường dẫn thư mục hoặc file con cụ thể để giới hạn tìm kiếm (tùy chọn)."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Đọc nội dung của một file trong workspace theo đường dẫn và khoảng dòng.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Đường dẫn tương đối hoặc tuyệt đối tới file cần đọc."
                            },
                            "line_range": {
                                "type": "string",
                                "description": "Khoảng dòng cần đọc, ví dụ: '1-50', '20-100'. Bỏ trống để đọc từ đầu."
                            }
                        },
                        "required": ["path"]
                    }
                }
            }
        ]


# ==========================================
# 2. AGENT QWEN2.5-CODER-7B
# ==========================================

class QwenCoderAgent:
    """Agent sử dụng model Qwen2.5-Coder-7B với ReAct loop & Tool execution."""

    SYSTEM_PROMPT = """Bạn là một Chuyên gia Kỹ thuật Phần mềm và Chuyên viên Phân tích Mã nguồn cấp cao.
Nhiệm vụ của bạn là trả lời các câu hỏi kỹ thuật về mã nguồn trong workspace một cách chính xác, sâu sắc và có căn cứ rõ ràng.

Bạn được cung cấp 2 công cụ quan trọng:
1. `search_grep(query, path)`: Tìm kiếm vị trí khai báo hàm, class, từ khóa, interface, v.v. trong mã nguồn.
2. `read_file(path, line_range)`: Đọc mã nguồn chi tiết của một file theo số dòng.

QUY TẮC BẮT BUỘC KHI LÀM VIỆC:
- BƯỚC 1: LUÔN bắt đầu bằng việc dùng `search_grep` để tìm vị trí xuất hiện của từ khóa, class, method.
  * TUYỆT ĐỐI KHÔNG gọi `read_file` ở Bước 1 khi chưa có kết quả `search_grep`.
  * TUYỆT ĐỐI KHÔNG tự bịa hoặc suy đoán đường dẫn file (ví dụ: KHÔNG đoán các thư mục ảo như `com/example/...`).
- BƯỚC 2 TRỞ ĐI: Dựa vào kết quả `search_grep` trả về, nhìn chính xác đường dẫn file thực tế trong workspace (ví dụ: `java/src/Main.java`, `java/src/engine/EventDispatcher.java`) và dùng `read_file` để đọc nội dung.
- NẾU GẶP LỖI FILE KHÔNG TỒN TẠI: Dừng lại ngay, xem lại danh sách file mà `search_grep` đã tìm thấy để lấy đúng file.
- KHI ĐÃ ĐỦ THÔNG TIN: Đưa ra câu trả lời chi tiết:
  + Nêu rõ tên module / package / file và số dòng tham khảo.
  + Giải thích nguyên lý và logic triển khai của hàm/class đó.
  + Trích dẫn đoạn mã ngắn nếu cần."""

    def __init__(
        self,
        workspace_dir: str,
        model_name: str = "qwen2.5-coder:7b",
        base_url: str = "http://127.0.0.1:11434/v1",
        api_key: str = "ollama",
        temperature: float = 0.2,
        max_steps: int = 8
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.tools = WorkspaceTools(str(self.workspace_dir))
        self.model_name = model_name
        self.temperature = temperature
        self.max_steps = max_steps
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=60.0)

    def _execute_tool_call(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Thực thi tool theo tên và tham số."""
        print(f"  [Tool Action] 🛠️  Gọi tool: {tool_name} với args: {args}")
        try:
            if tool_name == "read_file":
                path = args.get("path", "")
                line_range = args.get("line_range", None)
                return self.tools.read_file(path, line_range)
            elif tool_name == "search_grep":
                query = args.get("query", "")
                path = args.get("path", None)
                return self.tools.search_grep(query, path)
            else:
                return f"[Error] Không hỗ trợ tool: {tool_name}"
        except Exception as e:
            return f"[Tool Execution Error] {str(e)}"

    def _extract_tool_calls_fallback(self, content: str) -> List[Dict[str, Any]]:
        """
        Trích xuất tool call khi model Qwen output JSON hoặc text call trực tiếp 
        trong trường hợp API không map vào `message.tool_calls`.
        """
        calls = []
        if not content:
            return calls

        # 1. Thử bắt các khối JSON trong ```json { ... } ```
        json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if "name" in data and ("arguments" in data or "parameters" in data):
                    args = data.get("arguments", data.get("parameters", {}))
                    calls.append({"name": data["name"], "arguments": args})
            except Exception:
                pass
        if calls:
            return calls

        # 2. Thử parse toàn bộ content nếu là 1 JSON object
        trimmed = content.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                data = json.loads(trimmed)
                if "name" in data and ("arguments" in data or "parameters" in data):
                    args = data.get("arguments", data.get("parameters", {}))
                    calls.append({"name": data["name"], "arguments": args})
                    return calls
            except Exception:
                pass

        # 3. Thử tìm regex pattern {"name": "...", "arguments": {...}}
        pattern = r'\{\s*"name"\s*:\s*"([a-zA-Z0-9_-]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}'
        for match in re.finditer(pattern, content, re.DOTALL):
            try:
                name = match.group(1)
                args = json.loads(match.group(2))
                calls.append({"name": name, "arguments": args})
            except Exception:
                pass

        return calls

    def answer_question(self, question: str) -> str:
        """
        Xử lý câu hỏi qua vòng lặp ReAct:
        LLM <-> Workspace Tools -> Final Answer
        """
        print(f"\n=======================================================")
        print(f"❓ CÂU HỎI: {question}")
        print(f"=======================================================")

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Workspace hiện tại: {self.workspace_dir}\n\nCâu hỏi: {question}"}
        ]

        step = 0
        last_signature = None

        while step < self.max_steps:
            step += 1
            print(f"\n[Bước {step}/{self.max_steps}] Đang suy nghĩ...")

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=WorkspaceTools.get_tool_definitions(),
                    temperature=self.temperature
                )
            except Exception as e:
                return f"[Lỗi kết nối tới LLM {self.model_name}]: {str(e)}"

            msg = response.choices[0].message
            content = msg.content or ""
            raw_tool_calls = msg.tool_calls

            # Trích xuất các yêu cầu gọi tool
            calls_to_execute = []
            if raw_tool_calls:
                for tc in raw_tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except Exception:
                        fn_args = {}
                    calls_to_execute.append({
                        "id": tc.id,
                        "name": fn_name,
                        "arguments": fn_args
                    })
            else:
                fallback_calls = self._extract_tool_calls_fallback(content)
                for idx, fc in enumerate(fallback_calls):
                    calls_to_execute.append({
                        "id": f"call_fallback_{step}_{idx}",
                        "name": fc["name"],
                        "arguments": fc["arguments"]
                    })

            # Nếu không có tool call nào -> Đây là câu trả lời cuối cùng
            if not calls_to_execute:
                print(f"[Hoàn thành] Đã có câu trả lời cuối cùng sau {step} bước.\n")
                return content

            # Kiểm tra lặp tool call (Loop detection)
            current_signature = json.dumps(
                [(c["name"], sorted(c["arguments"].items())) for c in calls_to_execute],
                sort_keys=True
            )
            if current_signature == last_signature:
                print("  [Cảnh báo] Phát hiện vòng lặp gọi tool giống hệt bước trước. Chèn chỉ dẫn phá lặp...")
                messages.append({
                    "role": "user",
                    "content": (
                        "[CẢNH BÁO HỆ THỐNG]: Bạn đang gọi lại các công cụ và tham số giống hệt bước trước! "
                        "Vui lòng không lặp lại thao tác này. Hãy nhìn vào kết quả search_grep đã có ở trên để đọc "
                        "đúng file thực tế, hoặc tổng hợp thông tin và đưa ra câu trả lời cuối cùng ngay bây giờ."
                    )
                })
                continue

            last_signature = current_signature

            # Lưu lại message của assistant
            messages.append(msg)

            step_results = []
            for call in calls_to_execute:
                t_name = call["name"]
                t_args = call["arguments"]
                t_id = call.get("id")

                result = self._execute_tool_call(t_name, t_args)
                
                # In tóm tắt kết quả tool ra console
                res_lines = result.strip().split("\n")
                preview = res_lines[0] if res_lines else ""
                if len(res_lines) > 1:
                    preview += f" ... (+{len(res_lines) - 1} dòng khác)"
                print(f"  [Tool Result] 📄 {preview}")

                step_results.append((t_name, t_id, result))

            # Gửi kết quả tool về cho LLM
            if raw_tool_calls:
                for t_name, t_id, result in step_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": t_id,
                        "name": t_name,
                        "content": result
                    })
            else:
                # Fallback: gộp vào một tin nhắn rõ ràng, tránh model bị confused
                combined_text_parts = []
                for t_name, _, result in step_results:
                    combined_text_parts.append(f"=== KẾT QUẢ CÔNG CỤ: {t_name} ===\n{result}")
                combined_text_parts.append(
                    "\n[HƯỚNG DẪN TIẾP THEO]: Dựa vào kết quả các file thực tế ở trên, hãy đọc file cụ thể "
                    "hoặc nếu đã có đủ thông tin, hãy đưa ra câu trả lời hoàn chỉnh."
                )
                messages.append({
                    "role": "user",
                    "content": "\n\n".join(combined_text_parts)
                })

        # Nếu đạt tối đa số bước
        print(f"[Cảnh báo] Đã đạt giới hạn tối đa {self.max_steps} bước suy luận.")
        messages.append({
            "role": "user",
            "content": "Hãy tổng hợp tất cả các thông tin đã tìm thấy ở trên và đưa ra câu trả lời cuối cùng ngay bây giờ."
        })
        final_res = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature
        )
        return final_res.choices[0].message.content or "Không thể tạo câu trả lời hoàn chỉnh."


# ==========================================
# 3. QUẢN LÝ VÀ ĐỌC CÂU HỎI TỪ THƯ MỤC
# ==========================================

def load_questions_from_path(target_path: str) -> List[Dict[str, Any]]:
    """
    Đọc câu hỏi từ đường dẫn được chỉ định (có thể là thư mục hoặc file cụ thể).
    Hỗ trợ định dạng:
    - .json: Danh sách câu hỏi chuỗi hoặc danh sách object [{'id': ..., 'question': ...}]
    - .txt / .md: Mỗi dòng là một câu hỏi hoặc câu hỏi đánh số '1. ...', 'Q: ...'
    """
    path_obj = Path(target_path).resolve()
    if not path_obj.exists():
        raise FileNotFoundError(f"Đường dẫn không tồn tại: {target_path}")

    files = []
    if path_obj.is_file():
        files = [path_obj]
    else:
        for root, _, filenames in os.walk(path_obj):
            for fn in filenames:
                ext = Path(fn).suffix.lower()
                if ext in {".txt", ".json", ".md", ".jsonl"}:
                    files.append(Path(root) / fn)

    questions = []
    q_counter = 1

    for f in sorted(files):
        ext = f.suffix.lower()
        try:
            with open(f, "r", encoding="utf-8") as fp:
                raw_text = fp.read().strip()
                if not raw_text:
                    continue

                if ext in {".json", ".jsonl"}:
                    try:
                        data = json.loads(raw_text)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, str) and item.strip():
                                    questions.append({
                                        "id": f"Q{q_counter:03d}",
                                        "source_file": str(f.name),
                                        "question": item.strip()
                                    })
                                    q_counter += 1
                                elif isinstance(item, dict):
                                    q_text = item.get("question") or item.get("prompt") or item.get("content") or ""
                                    if q_text:
                                        questions.append({
                                            "id": item.get("id", f"Q{q_counter:03d}"),
                                            "source_file": str(f.name),
                                            "question": str(q_text).strip()
                                        })
                                        q_counter += 1
                        elif isinstance(data, dict):
                            # Có thể là map {id: question} hoặc object đơn
                            for k, v in data.items():
                                if isinstance(v, str) and v.strip():
                                    questions.append({
                                        "id": str(k),
                                        "source_file": str(f.name),
                                        "question": v.strip()
                                    })
                                    q_counter += 1
                    except json.JSONDecodeError:
                        # Fallback đọc theo dòng nếu jsonl
                        for line in raw_text.splitlines():
                            line = line.strip()
                            if line:
                                try:
                                    item = json.loads(line)
                                    q_text = item.get("question") or item.get("prompt") or line
                                    questions.append({
                                        "id": f"Q{q_counter:03d}",
                                        "source_file": str(f.name),
                                        "question": q_text
                                    })
                                    q_counter += 1
                                except Exception:
                                    pass

                elif ext in {".txt", ".md"}:
                    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
                    for line in lines:
                        # Bỏ qua các tiêu đề markdown đơn thuần như # Questions
                        if line.startswith("# ") and len(line.split()) < 3:
                            continue
                        # Bỏ qua comments
                        if line.startswith("//") or line.startswith("<!--"):
                            continue
                        
                        # Chuẩn hóa nếu bắt đầu bằng "1. ", "Câu 1:", "Q:"
                        cleaned = re.sub(r"^(?:Câu\s*\d+[\s:.-]*|\d+[\s:.-]+|Q\d*[\s:.-]+)", "", line).strip()
                        if len(cleaned) >= 5:
                            questions.append({
                                "id": f"Q{q_counter:03d}",
                                "source_file": str(f.name),
                                "question": cleaned
                            })
                            q_counter += 1
        except Exception as e:
            print(f"[Warning] Bỏ qua file '{f.name}' do lỗi đọc: {e}")

    return questions


# ==========================================
# 4. LƯU VÀ XUẤT BÁO CÁO KẾT QUẢ
# ==========================================

def save_results(results: List[Dict[str, Any]], output_dir: str):
    """Lưu kết quả ra file JSON và Markdown tổng hợp."""
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = out_path / f"answers_{timestamp}.json"
    md_file = out_path / f"answers_{timestamp}.md"

    # 1. Lưu file JSON
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 2. Lưu file Markdown
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# BÁO CÁO TRẢ LỜI CÂU HỎI VỀ MÃ NGUỒN WORKSPACE\n\n")
        f.write(f"- **Thời gian chạy**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Tổng số câu hỏi**: {len(results)}\n\n")
        f.write("---\n\n")

        for r in results:
            f.write(f"## [{r.get('id', 'N/A')}] {r['question']}\n\n")
            f.write(f"*(Nguồn: `{r.get('source_file', 'trực tiếp')}`)*\n\n")
            f.write("### Câu trả lời của Qwencoder2.5-7B:\n\n")
            f.write(f"{r['answer']}\n\n")
            f.write("---\n\n")

    print(f"\n=======================================================")
    print(f"🎉 Đã lưu kết quả thành công:")
    print(f"  📁 File Markdown : {md_file}")
    print(f"  📁 File JSON     : {json_file}")
    print(f"=======================================================")


# ==========================================
# 5. CHƯƠNG TRÌNH CHÍNH (MAIN CLI)
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description="Agent Qwen2.5-Coder-7B trả lời câu hỏi mã nguồn sử dụng tools read_file và search_grep."
    )
    parser.add_argument(
        "-w", "--workspace",
        type=str,
        default=".",
        help="Đường dẫn tới workspace mã nguồn cần tra cứu (mặc định: thư mục hiện tại)."
    )
    parser.add_argument(
        "-q", "--questions",
        type=str,
        default=None,
        help="Đường dẫn thư mục hoặc file chứa các câu hỏi cần trả lời."
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="./qa_results",
        help="Thư mục lưu báo cáo kết quả trả lời (mặc định: ./qa_results)."
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="qwen2.5-coder:7b",
        help="Tên model Ollama (mặc định: qwen2.5-coder:7b)."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="http://127.0.0.1:11434/v1",
        help="URL Ollama OpenAI-compatible endpoint (mặc định: http://127.0.0.1:11434/v1)."
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Chạy ở chế độ tương tác (nhập từng câu hỏi trực tiếp từ terminal)."
    )

    args = parser.parse_args()

    # Nhắc nhập nếu chạy trực tiếp không có tham số
    workspace_path = args.workspace
    if workspace_path == "." and not args.questions and not args.interactive:
        print("=== CẤU HÌNH AGENT QWEN2.5-CODER-7B ===")
        user_ws = input(f"Nhập đường dẫn workspace mã nguồn [Mặc định: {os.getcwd()}]: ").strip()
        if user_ws:
            workspace_path = user_ws

        user_q = input("Nhập đường dẫn thư mục (hoặc file) chứa câu hỏi [Để trống để vào chế độ hỏi đáp tương tác]: ").strip()
        if user_q:
            args.questions = user_q
        else:
            args.interactive = True

    workspace_dir = Path(workspace_path).resolve()
    print(f"\n📂 Workspace: {workspace_dir}")
    print(f"🤖 Model    : {args.model}")
    print(f"🔗 Ollama   : {args.host}")

    agent = QwenCoderAgent(
        workspace_dir=str(workspace_dir),
        model_name=args.model,
        base_url=args.host
    )

    # Chế độ tương tác
    if args.interactive:
        print("\n💬 ĐÃ VÀO CHẾ ĐỘ TƯƠNG TÁC (Gõ 'exit' hoặc 'quit' để thoát)")
        while True:
            try:
                user_question = input("\n👉 Nhập câu hỏi: ").strip()
                if not user_question:
                    continue
                if user_question.lower() in {"exit", "quit", "q"}:
                    print("Tạm biệt!")
                    break
                answer = agent.answer_question(user_question)
                print(f"\n💡 [CÂU TRẢ LỜI]:\n{answer}\n")
            except (KeyboardInterrupt, EOFError):
                print("\nĐã hủy.")
                break
        return

    # Chế độ đọc câu hỏi từ thư mục/file chỉ định
    if not args.questions:
        print("[Lỗi] Bạn cần chỉ định đường dẫn câu hỏi qua tham số -q / --questions hoặc dùng -i để chạy tương tác.")
        sys.exit(1)

    print(f"🔍 Đang quét câu hỏi từ: {args.questions} ...")
    questions = load_questions_from_path(args.questions)

    if not questions:
        print(f"[Cảnh báo] Không tìm thấy câu hỏi hợp lệ nào trong '{args.questions}'.")
        return

    print(f"✅ Đã tìm thấy {len(questions)} câu hỏi cần xử lý.\n")

    results = []
    for idx, item in enumerate(questions, start=1):
        print(f"\n-------------------------------------------------------")
        print(f"Tiến độ: [{idx}/{len(questions)}] ID: {item.get('id')}")
        answer = agent.answer_question(item["question"])
        results.append({
            "id": item.get("id"),
            "source_file": item.get("source_file"),
            "question": item["question"],
            "answer": answer
        })
        print(f"\n[Kết quả {item.get('id')}]:\n{answer}\n")

    # Lưu kết quả
    save_results(results, args.output)


if __name__ == "__main__":
    main()
