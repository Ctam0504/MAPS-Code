"""
multi_agent_system.agents.tester_agent
====================================
Agent Tester: Tiếp nhận task, mã nguồn các tệp và ngôn ngữ từ Planner/Coder,
sinh kịch bản kiểm thử (Test Harness) đa tệp cho Python, Java, C,
và cập nhật lại testcase khi nhận chỉ thị lỗi Testcase từ Reviewer.
"""

from typing import Dict, Optional
from .base_agent import BaseAgent
from .. import config
import re
import os

class TesterAgent(BaseAgent):
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            model_name=model_name or config.TESTER_MODEL,
            base_url=base_url,
            temperature=0.2
        )

    def _get_test_format_instructions(self, target_language: str) -> str:
        lang_lower = target_language.lower()
        if lang_lower == "python":
            return """
ĐỊNH DẠNG TESTCASE CHO PYTHON:
Viết một lớp kế thừa `unittest.TestCase` kiểm tra toàn diện chức năng của hệ thống đa tệp.
Ví dụ:
import unittest
# import các module từ dự án

class TestMultiFileProject(unittest.TestCase):
    def test_feature_a(self):
        # gọi hàm/class
        self.assertIsNotNone(...)
"""
        elif lang_lower == "java":
            return """
ĐỊNH DẠNG TESTCASE CHO JAVA:
Sinh một test class JUnit 5 tên `TestHarness` trong default package.
1. Dùng `org.junit.jupiter.api.Test` và assertion từ `org.junit.jupiter.api.Assertions`.
2. Mỗi test là một method `void` không tham số có annotation `@Test`; không viết hàm `main`.
3. Sandbox sẽ tự compile source và test, phát hiện/chạy test bằng JUnit, và trả lỗi khi assertion fail.
4. TestHarness phải ở default package; import chính xác package public của source.
5. Chỉ khởi tạo đối tượng theo constructor và signature thực sự có trong source.
Ví dụ:
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class TestHarness {
    @Test
    void testFeature() {
        assertEquals(expected, actual, "mô tả ngắn");
    }
}
"""
        else:  # c
            return """
ĐỊNH DẠNG TESTCASE CHO C:
Viết một file C hoàn chỉnh có hàm `int main()` và các câu lệnh `assert(...)`.
Ví dụ:
#include <stdio.h>
#include <assert.h>
// #include các file header của dự án

int main() {
    assert(...);
    printf("[PASS] All tests passed.\\n");
    return 0;
}
"""

    def generate_tests(
        self,
        task_goal: str,
        files_dict: Dict[str, str],
        target_language: str,
        history_feedback: str = ""
    ) -> str:
        """
        Sinh mã nguồn Test Harness kiểm thử toàn bộ hệ thống đa tệp.
        """
        code_overview = ""
        for filepath, content in files_dict.items():
            code_overview += f"\n--- TỆP: `{filepath}` ---\n```{target_language}\n{content}\n```\n"

        history_section = f"\n### [LỊCH SỬ PHẢN HỒI]:\n{history_feedback}\n" if history_feedback else ""
        fmt_instruction = self._get_test_format_instructions(target_language)

        prompt = f"""BẠN LÀ SENIOR QA ENGINEER & AUTOMATION TEST EXPERT ({target_language.upper()}).
Nhiệm vụ: Viết bộ kịch bản kiểm thử (Test Suite) toàn diện cho dự án đa tệp dưới đây.

### [YÊU CẦU BÀI TOÁN GỐC]:
{task_goal}

### [MÃ NGUỒN CÁC TỆP ĐÃ SINH]:
{code_overview}
{history_section}
### [QUY TẮC KIỂM THỬ]:
1. Kiểm tra các chức năng chính và các trường hợp biên (edge cases).
2. Kiểm tra sự phối hợp (integration) giữa các module/tệp tin.
3. Test case PHẢI khách quan và tuân thủ đúng yêu cầu bài toán. Không tự bịa ra điều kiện vô lý.
4. Khi viết test assertion, luôn in ra giá trị thực tế nếu kiểm tra thất bại (VD: Result, Expected).
{fmt_instruction}
### [NGỮ CẢNH]:
1. Mã kiểm thử sinh ra nằm ở thư mục gốc của dự án. Cùng cấp với filepath.
2. Dựa vào ngữ cảnh sinh ra import/include chính xác.
### [YÊU CẦU ĐẦU RA]:
CHỈ TRẢ VỀ DUY NHẤT MÃ KIỂM THỬ trong khối ```{target_language} ... ```. Không giải thích gì thêm.
"""

        raw_resp = self.call_llm(prompt)
        clean_code = self.extract_code_block(raw_resp, language=target_language)
        return clean_code if clean_code else raw_resp.strip()

    def fix_tests(
        self,
        task_goal: str,
        files_dict: Dict[str, str],
        current_tests: str,
        target_language: str,
        reviewer_instructions: str,
        error_log: str
    ) -> str:
        """
        Sửa đổi lại testcase khi Reviewer xác định lỗi do Tester viết sai assertion hoặc điều kiện.
        """
        code_overview = ""
        for filepath, content in files_dict.items():
            code_overview += f"\n--- TỆP: `{filepath}` ---\n```{target_language}\n{content}\n```\n"

        fmt_instruction = self._get_test_format_instructions(target_language)

        prompt = f"""BẠN LÀ QA ENGINEER ({target_language.upper()}).
Testcase của bạn đã gặp **LỖI TESTCASE (TESTER FAULTY)**: Reviewer xác định assertion sai kỳ vọng, kiểm tra điều kiện không có trong đề bài, hoặc gọi sai kiểu dữ liệu.

### [YÊU CẦU BÀI TOÁN GỐC]:
{task_goal}

### [MÃ NGUỒN DỰ ÁN]:
{code_overview}

### [TESTCASE HIỆN TẠI]:
```{target_language}
{current_tests}
```

### [NHẬT KÝ LỖI SANDBOX]:
{error_log}

### [CHỈ THỊ SỬA TESTCASE TỪ REVIEWER]:
{reviewer_instructions}

{fmt_instruction}

### [NHIỆM VỤ]:
1. Phân tích chỉ thị của Reviewer và chỉ ra chính xác các test assertion / điều kiện cần sửa.
2. Tuân thủ tuyệt đối chỉ thị sửa lỗi.
3. Viết lại bộ testcase hoàn chỉnh đã khắc phục toàn bộ lỗi trên.
### [NGỮ CẢNH]:
1. Mã kiểm thử sinh ra nằm ở thư mục gốc của dự án. Cùng cấp với filepath.
2. Dựa vào ngữ cảnh sinh ra import/include chính xác.
CHỈ TRẢ VỀ MÃ KIỂM THỬ trong khối ```{target_language} ... ```. Không giải thích gì thêm.
"""

        # Ensure clean_code is defined even if LLM returns no code block
        clean_code = ""
        raw_resp = self.call_llm(prompt)
        clean_code = self.extract_code_block(raw_resp, language=target_language)

        # Dynamic include fix for C test harness:
        # For each #include "header.h" without a path, locate the actual file in the workspace
        # (provided via files_dict) and replace with the correct relative path.
        if target_language.lower() == "c":
            # Find all include statements
            include_pattern = r"#include\s+\"([^\"]+)\""
            for match in re.finditer(include_pattern, clean_code):
                inc = match.group(1)
                # Skip if include already contains a directory separator
                if os.path.sep in inc:
                    continue
                # Search for the header file in the workspace files_dict
                matched_path = None
                for filepath in files_dict.keys():
                    if os.path.basename(filepath) == inc:
                        matched_path = filepath
                        break
                if matched_path:
                    # Use the workspace-relative path (e.g., "c/calculator.h")
                    rel_path = matched_path.replace(os.path.sep, "/")
                    clean_code = clean_code.replace(f'#include "{inc}"', f'#include "{rel_path}"')
                # End of include handling
        # Auto-import missing standard libraries for Java test harness
        if target_language.lower() == "java":
            java_imports = []
            if re.search(r"\b(Map|List|Set|HashMap|ArrayList|HashSet)\b", clean_code):
                if "import java.util" not in clean_code:
                    java_imports.append("import java.util.*;")
            if re.search(r"\b(File|BufferedReader|BufferedWriter|FileReader|FileWriter|IOException)\b", clean_code):
                if "import java.io" not in clean_code:
                    java_imports.append("import java.io.*;")
            
            if java_imports:
                clean_code = "\n".join(java_imports) + "\n" + clean_code


        return clean_code if clean_code else raw_resp.strip()
