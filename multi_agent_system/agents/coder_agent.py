"""
multi_agent_system.agents.coder_agent
====================================
Agent Coder: Tiếp nhận task từ Planner, sinh mã nguồn từng tệp tin
dựa trên ngôn ngữ đích (Python, Java, C), tích lũy ngữ cảnh các tệp đã tạo,
và tiến hành sửa đổi mã nguồn khi có chỉ thị lỗi Local từ Reviewer.
"""

from typing import Dict, Optional, List, Any
from .base_agent import BaseAgent
from ..schemas import FileSpec, MultiFilePlan
from .. import config

class CoderAgent(BaseAgent):
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            model_name=model_name or config.CODER_MODEL,
            base_url=base_url,
            temperature=0.1
        )

    def _get_language_rules(self, lang: str) -> str:
        lang_lower = lang.lower()
        if lang_lower == "java":
            return """
QUY TẮC BẮT BUỘC CHO JAVA:
1. File phải có khai báo package ở dòng đầu tiên nếu nằm trong thư mục con (ví dụ: file `models/User.java` phải có `package models;`).
2. Tên public class PHẢI TRÙNG KHỚP 100% với tên file (ví dụ `public class User` cho file `User.java`).
3. BẮT BUỘC IMPORT ĐẦY ĐỦ các class thuộc các package khác (Ví dụ: dùng `User`, `Ticket` trong controllers hay services thì PHẢI có `import models.User;` hoặc `import models.*;`). TUYỆT ĐỐI KHÔNG ĐỂ THIẾU IMPORT.
4. Triển khai đầy đủ logic, không để hàm rỗng, không để comment TODO.
"""
        elif lang_lower in ["c", "cpp"]:
            return """
QUY TẮC BẮT BUỘC CHO C:
1. Mọi đường dẫn header nội bộ phải lấy từ `dependencies` của FileSpec và giữ nguyên đầy đủ filepath tương đối từ project root, dùng dấu `/` trong câu lệnh include. Ví dụ dependency `include/main.h` thì viết `#include "include/main.h"`; không rút về basename (`main.h`) hoặc tự đổi thành đường dẫn tương đối với thư mục source.
2. Dùng `#include "..."` cho header nội bộ của dự án; dùng `#include <...>` cho header chuẩn/thư viện bên ngoài.
3. Nếu cần header nội bộ nhưng header đó không có trong `dependencies`, không tự đoán tên hay đường dẫn; chỉ dùng các dependency đã khai báo.
4. Nếu là file Header (`.h`): BẮT BUỘC có Include Guards (`#ifndef ...`, `#define ...`, `#endif`), khai báo các kiểu cần chia sẻ và nguyên mẫu hàm liên quan.
5. Nếu là file Source (`.c`): include các header nội bộ cần thiết theo quy tắc trên và triển khai đầy đủ thân hàm.
6. Sử dụng đúng header chuẩn cần thiết (`stdlib.h`, `stdio.h`, `string.h`, `stdbool.h`...); không include thừa hoặc thay header chuẩn bằng header dự án.
7. Triển khai đầy đủ logic, không để comment TODO hay placeholder.
"""
        else:  # python
            return """
QUY TẮC BẮT BUỘC CHO PYTHON:
1. Dùng import chuẩn xác dựa trên danh sách các tệp phụ thuộc.
2. Viết mã nguồn hoàn chỉnh với đầy đủ thân hàm/class và câu lệnh return.
3. Không chèn comment TODO hoặc placeholder.
"""

    def generate_file(
        self,
        file_spec: FileSpec,
        created_files_context: Dict[str, str],
        target_language: str,
        task_goal: str,
        feedback: Optional[str] = None
    ) -> str:
        """
        Sinh mã nguồn cho CREATE/MODIFY hoặc giữ nguyên nội dung với KEEP.
        """
        action = file_spec.action.strip().upper()
        if action == "KEEP":
            if file_spec.filepath not in created_files_context:
                raise ValueError(
                    f"FileSpec action KEEP requires existing content for '{file_spec.filepath}'."
                )
            return created_files_context[file_spec.filepath]

        dep_context = ""
        for dep in file_spec.dependencies:
            if dep in created_files_context:
                dep_context += f"\n--- NỘI DUNG TỆP PHỤ THUỘ `{dep}` ---\n{created_files_context[dep]}\n"

        existing_files_list = list(created_files_context.keys())
        internal_dependencies = file_spec.dependencies
        external_dependencies = file_spec.external_dependencies
        lang_rules = self._get_language_rules(target_language)

        feedback_section = ""
        if feedback:
            feedback_section = f"""
### ⚠️ [CẢNH BÁO: CÁC LỖI THỰC THI/BIÊN DỊCH Ở VÒNG TRƯỚC - TUYỆT ĐỐI KHÔNG TÁI PHẠM]:
{feedback}
YÊU CẦU ĐẶC BIỆT: Khắc phục triệt để các lỗi biên dịch, thiếu import hoặc sai interface nêu trên!
"""

        existing_code_section = ""
        current_existing = created_files_context.get(file_spec.filepath, "")
        if action == "MODIFY" and current_existing:
            existing_code_section = f"""
### [MÃ NGUỒN TIỀN SẮP XẾP HIỆN CÓ CỦA TỆP `{file_spec.filepath}` CẦN SỬA ĐỔI / HOÀN THIỆN]:
```{target_language}
{current_existing}
```
CHỈ THỊ SỬA ĐỔI: Kế thừa và giữ nguyên các hàm/class đã viết đúng, chỉnh sửa hoặc bổ sung thêm logic để thỏa mãn yêu cầu: {file_spec.interface_summary}.
"""

        prompt = f"""BẠN LÀ SENIOR SOFTWARE ENGINEER CHUYÊN NGHIỆP VỀ **{target_language.upper()}**.
Nhiệm vụ: Viết mã nguồn HOÀN CHỈNH cho tệp tin: `{file_spec.filepath}`.

### [YÊU CẦU BÀI TOÁN GỐC]:
{task_goal}

### [THÔNG SỐ THIẾT KẾ CỦA TỆP]:
- Đường dẫn: `{file_spec.filepath}`
- Hành động: `{file_spec.action}`
- Mục đích: {file_spec.purpose}
- Interface yêu cầu: {file_spec.interface_summary}
- File phụ thuộc nội bộ (filepath chính xác): {internal_dependencies}
- Thư viện/package bên ngoài: {external_dependencies}

### [DANH SÁCH CÁC TỆP ĐÃ CÓ TRONG WORKSPACE]:
{existing_files_list}
{existing_code_section}
{dep_context}
{feedback_section}
{lang_rules}

### [YÊU CẦU ĐẦU RA NGHIÊM NGẶT]:
1. CHỈ TRẢ VỀ DUY NHẤT MÃ NGUỒN trong một khối ```{target_language} ... ```.
2. Tuyệt đối KHÔNG giải thích dông dài bên ngoài khối code.
3. Tái sử dụng chính xác tên Class, Struct, Hàm, Tham số từ các tệp phụ thuộc đã tạo.
4. Triển khai đầy đủ 100% thân hàm, không để placeholder hay pass lửng lơ.
5. ĐẢM BẢO IMPORT ĐẦY ĐỦ các class/struct được dùng trong file này từ các package/tệp khác.
"""

        raw_resp = self.call_llm(prompt)
        clean_code = self.extract_code_block(raw_resp, language=target_language)
        if not clean_code:
            clean_code = raw_resp.strip()

        return clean_code

    def generate_all_files(
        self,
        plan: MultiFilePlan,
        task_goal: str,
        initial_files: Optional[Dict[str, str]] = None,
        output_dir: Optional[str] = None,
        shared_memory: Optional[Any] = None,
        feedback: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Sinh toàn bộ các file theo thứ tự Topo (execution_order) trong kế hoạch.
        Kế thừa toàn bộ các file được truyền vào (initial_files).
        Hỗ trợ lọc ngữ cảnh chia sẻ qua shared_memory và kế thừa feedback sửa lỗi.
        """
        created_files: Dict[str, str] = dict(initial_files) if initial_files else {}
        spec_map = {f.filepath: f for f in plan.files}

        order = plan.execution_order
        if not order:
            order = [f.filepath for f in plan.files]

        for filepath in order:
            if filepath not in spec_map:
                continue
            spec = spec_map[filepath]

            action = spec.action.strip().upper()
            if action == "KEEP":
                if filepath not in created_files:
                    raise ValueError(
                        f"FileSpec action KEEP requires existing content for '{filepath}'."
                    )
                print(f"   📁 [Coder] Giữ nguyên tệp hiện tại: {filepath}")
                continue

            action_label = "Sửa đổi" if action == "MODIFY" else "Sinh mới"
            print(f"   💻 [Coder] {action_label} tệp: {filepath} ({plan.target_language.upper()})...")

            # Lọc ngữ cảnh các tệp phụ thuộc/đã tạo nếu bật/tắt shared_memory
            files_context = created_files
            if shared_memory:
                files_context = shared_memory.get_coder_context(spec, created_files)

            code = self.generate_file(
                file_spec=spec,
                created_files_context=files_context,
                target_language=plan.target_language,
                task_goal=task_goal,
                feedback=feedback,
            )
            created_files[filepath] = code

            # Save file immediately if output_dir is provided
            if output_dir:
                import os
                full_path = os.path.join(output_dir, filepath.lstrip("/\\"))
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(code)
                print(f"   📁 [Coder] Đã ghi tệp: {full_path}")

        return created_files

    def fix_file(
        self,
        filepath: str,
        current_code: str,
        all_files: Dict[str, str],
        reviewer_instructions: str,
        error_log: str,
        target_language: str,
        task_goal: str
    ) -> str:
        """
        Sửa đổi mã nguồn của một tệp khi bị Reviewer báo lỗi Local.
        """
        lang_rules = self._get_language_rules(target_language)
        other_files = [f for f in all_files.keys() if f != filepath]

        prompt = f"""BẠN LÀ SENIOR SOFTWARE ENGINEER CHUYÊN SỬA LỖI **{target_language.upper()}**.
Tệp tin `{filepath}` gặp **LỖI CỤC BỘ (LOCAL ERROR)**: Lỗi cú pháp, logic tính toán bên trong hàm, hoặc runtime exception.

### [YÊU CẦU BÀI TOÁN GỐC]:
{task_goal}

### [MÃ NGUỒN HIỆN TẠI CỦA TỆP `{filepath}`]:
```{target_language}
{current_code}
```

### [NHẬT KÝ LỖI SANDBOX]:
{error_log}

### [CHỈ THỊ SỬA LỖI TỪ REVIEWER]:
{reviewer_instructions}

### [CÁC TỆP KHÁC TRONG DỰ ÁN]:
{other_files}

{lang_rules}

### [NHIỆM VỤ]:
Viết lại mã nguồn HOÀN CHỈNH của tệp `{filepath}` đã khắc phục triệt để lỗi trên.
CHỈ TRẢ VỀ DUY NHẤT MÃ NGUỒN trong khối ```{target_language} ... ```. Không giải thích gì thêm.
"""

        raw_resp = self.call_llm(prompt)
        clean_code = self.extract_code_block(raw_resp, language=target_language)
        return clean_code if clean_code else raw_resp.strip()
