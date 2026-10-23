"""
multi_agent_system.agents.planner_agent
======================================
Agent Planner: Tiếp nhận yêu cầu, phân tích cây thư mục bằng GraphRAG,
xác định ngôn ngữ qua công cụ, lập kế hoạch kiến trúc đa tệp và cập nhật plan
khi nhận phản hồi lỗi Global từ Reviewer.
"""

import os
import json
import re
from typing import Optional, Any, Dict, List
from pydantic import ValidationError

from .base_agent import BaseAgent
from ..schemas import MultiFilePlan, FileSpec, LanguageType
from ..tools.language_detector import detect_language_from_folder
from ..rag.ast_extractor import parse_codebase_to_graph_and_chunks
from ..rag.rag_pipeline import GraphRAGRetriever
from .. import config
from ..tools.draw import generate_ascii_tree

class PlannerAgent(BaseAgent):
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            model_name=model_name or config.PLANNER_MODEL,
            base_url=base_url,
            temperature=0.1
        )

    def _get_language_guidelines(self, lang: str) -> str:
        lang_lower = lang.lower()
        if lang_lower == "java":
            return """
QUY TẮC BẮT BUỘC DÀNH CHO JAVA (Pure JDK):
1. Mọi `filepath` phải có đuôi `.java` và tuân thủ chuẩn cấu trúc package (ví dụ: `models/User.java`, `services/UserService.java`).
2. Tên Class PHẢI TRÙNG KHỚP 100% với tên file `.java` (ví dụ: `public class User` trong `User.java`).
3. Khai báo `package` ở đầu mỗi file phù hợp với đường dẫn thư mục.
4. Đảm bảo import, dependency đầy đủ giữa các package dựa trên cây thư mục.
"""
        elif lang_lower in ["c", "cpp"]:
            return """
QUY TẮC BẮT BUỘC DÀNH CHO C:
1. Tạo đầy đủ các file Header (`.h`) cho interface/structs và file nguồn (`.c`) cho logic triển khai.
2. File Header PHẢI có Include Guards (`#ifndef ..._H`, `#define ..._H`, `#endif`).
3. Sử dụng `#include "relative_path/file.h"` chính xác dựa vào cây thư mục để liên kết giữa các module.
4. Tách biệt rõ ràng giữa khai báo (Header) và triển khai (Source code).
"""
        else:  # python
            return """
QUY TẮC BẮT BUỘC DÀNH CHO PYTHON:
1. Tất cả `filepath` phải có đuôi `.py`.
2. Sử dụng import tương đối/tuyệt đối chuẩn xác dựa trên cây thư mục đã lên kế hoạch.
3. Đảm bảo cấu trúc module rõ ràng, phân chia tầng hợp lý.
"""

    async def draw_folder_structure(self, folder: Optional[str]) -> str:
        if not folder or not os.path.exists(folder):
            structure = "(Thư mục không tồn tại / Dự án rỗng)\n"
        else:
            structure = generate_ascii_tree(folder)

        print(f"\n🌳 [Planner: Draw] Cây thư mục hiện tại:\n{structure}")
        return structure

    async def _retrieve_graphrag_context(self, folder: Optional[str]) -> str:
        if not folder or not os.path.exists(folder):
            return ""
        try:
            graph, _ = parse_codebase_to_graph_and_chunks(folder)
            if graph.number_of_nodes() == 0:
                return ""
            return GraphRAGRetriever.get_codebase_manifest(graph)
        except Exception as e:
            print(f"⚠️ [Planner] Bỏ qua trích xuất GraphRAG do lỗi: {e}")
            return ""

    def _sanitize_plan_dict(self, data: Dict[str, Any], default_lang: str) -> Dict[str, Any]:
        """
        Tiền xử lý và làm sạch Dict thô từ LLM trước khi nạp vào Pydantic 
        nhằm tránh các lỗi thường gặp như null, sai kiểu, thiếu list...
        """
        if not isinstance(data, dict):
            return {}

        # 1. target_language chuẩn hóa
        target_lang = str(data.get("target_language") or default_lang).lower().strip()
        data["target_language"] = target_lang

        # 2. Xử lý danh sách files
        raw_files = data.get("files", [])
        if not isinstance(raw_files, list):
            raw_files = []

        sanitized_files = []
        all_filepaths = []

        for f in raw_files:
            if not isinstance(f, dict) or not f.get("filepath"):
                continue

            filepath = str(f.get("filepath")).strip().replace("\\", "/")
            all_filepaths.append(filepath)

            # Chuẩn hóa action về dạng UPPERCASE chuẩn
            raw_action = str(f.get("action", "CREATE")).upper()
            if "MODIFY" in raw_action:
                action = "MODIFY"
            elif "KEEP" in raw_action:
                action = "KEEP"
            else:
                action = "CREATE"

            # Đảm bảo các field list không bao giờ là None
            deps = f.get("dependencies")
            if not isinstance(deps, list):
                deps = []

            ext_deps = f.get("external_dependencies")
            if not isinstance(ext_deps, list):
                ext_deps = []

            sanitized_files.append({
                "filepath": filepath,
                "action": action,
                "dependencies": [str(d) for d in deps if d],
                "external_dependencies": [str(e) for e in ext_deps if e],
                "purpose": str(f.get("purpose") or "Triển khai mã nguồn"),
                "interface_summary": str(f.get("interface_summary") or "")
            })

        data["files"] = sanitized_files

        # 3. Đồng bộ execution_order để tránh lỗi không khớp filepath
        exec_order = data.get("execution_order")
        if not isinstance(exec_order, list) or not exec_order:
            data["execution_order"] = all_filepaths
        else:
            cleaned_order = [str(x).strip().replace("\\", "/") for x in exec_order if str(x).strip()]
            for fp in all_filepaths:
                if fp not in cleaned_order:
                    cleaned_order.append(fp)
            data["execution_order"] = cleaned_order

        # 4. Các trường string mặc định
        if not data.get("architecture_pattern"):
            data["architecture_pattern"] = "Modular Architecture"
        if not data.get("rationale"):
            data["rationale"] = "Thiết kế phân tầng theo yêu cầu hệ thống."

        return data

    def _try_validate_or_retry(self, prompt: str, default_lang: str, max_retries: int = 2) -> Optional[MultiFilePlan]:
        """
        Gọi LLM, trích xuất JSON, làm sạch và Validate. Nếu lỗi, phản hồi lại ValidationError cho LLM sửa.
        """
        current_prompt = prompt
        
        for attempt in range(max_retries + 1):
            response_text = self.call_llm(current_prompt, format_json=True)
            json_obj = self.extract_json_object(response_text)

            if json_obj:
                sanitized_dict = self._sanitize_plan_dict(json_obj, default_lang)
                try:
                    return MultiFilePlan.model_validate(sanitized_dict)
                except ValidationError as ve:
                    print(f"⚠️ [Planner] Lỗi Pydantic ở lần thử {attempt + 1}: {ve}")
                    if attempt < max_retries:
                        current_prompt = f"""Dữ liệu JSON bạn vừa trả về gây ra lỗi Pydantic sau:
{str(ve)}

Hãy SỬA LẠI và chỉ trả về DUY NHẤT một JSON hợp lệ tuân thủ chính xác Schema. Không kèm Markdown hay lời dẫn."""
            else:
                print(f"⚠️ [Planner] Không parse được JSON ở lần thử {attempt + 1}")

        return None

    def _get_fallback_plan(self, resolved_lang: str) -> MultiFilePlan:
        """Tạo plan dự phòng nếu LLM hoàn toàn thất bại trong việc trả về JSON chuẩn."""
        ext = 'py' if resolved_lang == 'python' else ('java' if resolved_lang == 'java' else 'c')
        default_file = f"main.{ext}"
        return MultiFilePlan(
            target_language=resolved_lang,
            architecture_pattern="Single Module Fallback",
            execution_order=[default_file],
            files=[
                FileSpec(
                    filepath=default_file,
                    action="CREATE",
                    dependencies=[],
                    purpose="Triển khai toàn bộ giải pháp cho bài toán",
                    interface_summary="Tất cả các hàm và class cần thiết"
                )
            ],
            rationale="Fallback do LLM trả về cấu trúc không chuẩn."
        )

    async def plan_codebase(
        self, 
        task_prompt: str, 
        input_folder: Optional[str] = None, 
        target_language: Optional[str] = None
    ) -> MultiFilePlan:
        # 1. Xác định ngôn ngữ lập trình
        resolved_lang: Optional[str] = target_language
        if not resolved_lang and input_folder and os.path.exists(input_folder):
            detected, _ = detect_language_from_folder(input_folder)
            if detected:
                resolved_lang = detected.value

        if not resolved_lang and task_prompt:
            task_lower = task_prompt.lower()
            if any(k in task_lower for k in ["java", "spring", "maven", "gradle"]):
                resolved_lang = "java"
            elif any(k in task_lower for k in ["c++", "cpp", "ngôn ngữ c", "lập trình c"]):
                resolved_lang = "c"
            elif any(k in task_lower for k in ["python", "fastapi", "django"]):
                resolved_lang = "python"

        if not resolved_lang:
            resolved_lang = getattr(config, "DEFAULT_TARGET_LANGUAGE", "java")

        # 2. Phân tích ngữ cảnh
        graphrag_context = await self._retrieve_graphrag_context(input_folder)
        rag_section = f"\n### [Thông tin folder tập tin hiện tại]:\n{graphrag_context}\n" if graphrag_context else ""
        folder_structure = f"\n### [Cây thư mục hiện tại]:\n{await self.draw_folder_structure(input_folder)}\n"
        guidelines = self._get_language_guidelines(resolved_lang)
        json_schema_desc = """
Trả về DUY NHẤT một JSON Object tuyệt đối hợp lệ theo cấu trúc sau:
{
  "target_language": "%s",
  "architecture_pattern": "Mẫu kiến trúc sử dụng (vd: Clean Architecture, Modular)",
  "execution_order": ["filepath_leaf_1", "filepath_leaf_2", "filepath_root_main"],
  "files": [
    {
      "filepath": "đường dẫn tương đối của file kèm đuôi",
      "action": "CREATE hoặc MODIFY hoặc KEEP",
      "dependencies": ["relative_path/file chính xác từ manifest, ví dụ: src/include/user.h"],
      "external_dependencies": ["tên thư viện/package bên ngoài, ví dụ: stdio.h hoặc java.util.List"],
      "purpose": "mục đích và trách nhiệm của tệp",
      "interface_summary": "tóm tắt Class, Function signatures, Structs hoặc Headers"
    }
  ],
  "rationale": "giải thích ngắn gọn lý do phân chia cấu trúc"
}
""" % resolved_lang

        prompt = f"""BẠN LÀ MỘT HỆ THỐNG SYSTEM ARCHITECT AGENT CHUYÊN NGHIỆP.
Nhiệm vụ: Phân tích yêu cầu bài toán và thiết kế cấu trúc ĐA TỆP (Multi-File) hoàn chỉnh cho ngôn ngữ: **{resolved_lang.upper()}**.

### [YÊU CẦU BÀI TOÁN]:
{task_prompt}

{rag_section}

{folder_structure}

### [QUY TẮC THIẾT KẾ KIẾN TRÚC]:
### Nếu codebase rỗng:
1. Thiết kế module hóa sạch sẽ, tách biệt trách nhiệm (Single Responsibility).
2. Chuỗi trong mảng `execution_order` PHẢI KHỚP TỪNG KÝ TỰ với `filepath` trong danh sách `files`.
3. Sắp xếp `execution_order` theo thứ tự Topo: File độc lập (Data Models/Headers/Interfaces) đứng trước, file cài đặt đứng giữa, file tích hợp chính (Main/Service) đứng cuối cùng.
### Nếu codebase đã có sẵn:
Hãy kế thừa, tái sử dụng các tệp, class, struct, hàm và package sẵn có trong thư mục này, chuẩn hóa lại tên class/hàm/interface signatures giữa các file, hoặc bổ sung/loại bỏ file cần thiết.
+++ Quy tắc sửa lỗi:
- Tuân thủ yêu cầu bài toán, chỉ sửa đổi những file cần thiết, giữ nguyên các file đã đúng.
- Nếu cần tạo file mới, hãy thêm vào danh sách `files` với `action: "CREATE"`.
- Nếu file hiện tại cần sửa đổi, hãy đặt `action: "MODIFY"` và cập nhật `interface_summary` tương ứng.
- Nếu file hiện tại không cần sửa đổi, hãy giữ nguyên `action: "KEEP"` và không thay đổi nội dung.
{guidelines}
### [ĐỊNH DẠNG ĐẦU RA YÊU CẦU]:
Chỉ trả về JSON object thuần túy, không chèn lời mở đầu hay kết luận ngoài JSON.
{json_schema_desc}
"""

        # Gọi qua cơ chế Validate + Self-Retry + Sanitization
        plan = self._try_validate_or_retry(prompt, resolved_lang, max_retries=2)
        if plan:
            return plan

        return self._get_fallback_plan(resolved_lang)

    async def refine_plan(
        self,
        task_prompt: str,
        current_plan: MultiFilePlan,
        reviewer_instructions: str,
        error_log: str,
        current_folder: Optional[str] = None
    ) -> MultiFilePlan:
        """
        Cập nhật lại kế hoạch và cây thư mục khi Reviewer xác định lỗi Global.
        """
        graphrag_context = await self._retrieve_graphrag_context(current_folder)
        rag_section = f"\n### [Thông tin folder tập tin hiện tại]:\n{graphrag_context}\n" if graphrag_context else ""
        folder_structure = (
            f"\n### [Cây thư mục hiện tại]:\n"
            f"{await self.draw_folder_structure(current_folder)}\n"
        )
        guidelines = self._get_language_guidelines(current_plan.target_language)

        prompt = f"""BẠN LÀ SYSTEM ARCHITECT AGENT.
Kế hoạch đa tệp hiện tại của bạn đã gặp **LỖI TOÀN CỤC (GLOBAL ARCHITECTURE ERROR)**.
Yêu cầu bài toán: {task_prompt}
### [NHẬT KÝ LỖI SANDBOX]:
{error_log}

### [CHỈ THỊ SỬA ĐỔI TỪ REVIEWER]:
Dựa vào chỉ thị sửa đổi và nhật ký lỗi, hãy tìm ra lỗi ở đâu trong plan và chỉnh sửa lại kế hoạch kiến trúc đa tệp sao cho phù hợp với yêu cầu bài toán.
{reviewer_instructions}

{rag_section}

{folder_structure}

{guidelines}

### [NHIỆM VỤ]:
Hãy kế thừa, tái sử dụng các tệp, class, struct, hàm và package sẵn có trong thư mục này, chuẩn hóa, sửa đổi lại tên class/hàm/interface signatures giữa các file, hoặc bổ sung/loại bỏ file cần thiết.
### Quy tắc sửa lỗi:
- Tuân thủ yêu cầu bài toán, chỉ thị sửa lỗi và nhật ký lỗi, chỉ sửa đổi những file cần thiết, giữ nguyên các file đã đúng.
- Nếu cần tạo file mới, hãy thêm vào danh sách `files` với `action: "CREATE"`.
- Nếu file hiện tại cần sửa đổi, hãy đặt `action: "MODIFY"` và cập nhật `interface_summary` tương ứng.
- Nếu file hiện tại không cần sửa đổi, hãy giữ nguyên `action: "KEEP"` và không thay đổi nội dung.
Trả về DUY NHẤT một JSON Object hợp lệ của `MultiFilePlan`:
{{
  "target_language": "{current_plan.target_language}",
  "architecture_pattern": "{current_plan.architecture_pattern}",
  "execution_order": ["file1", "file2"],
  "files": [
    {{
      "filepath": "đường dẫn file",
      "action": "CREATE hoặc MODIFY hoặc KEEP",
      "dependencies": ["relative_path/file chính xác từ manifest, ví dụ: src/include/user.h"],
      "external_dependencies": ["tên thư viện/package bên ngoài, ví dụ: stdio.h hoặc java.util.List"],
      "purpose": "mục đích",
      "interface_summary": "tóm tắt interface/class/method cần chỉnh sửa"
    }}
  ],
  "rationale": "Lý do điều chỉnh"
}}
"""

        # Sử dụng try-validate-retry cả trong bước refine
        refined_plan = self._try_validate_or_retry(prompt, current_plan.target_language, max_retries=2)
        if refined_plan:
            return refined_plan

        return current_plan