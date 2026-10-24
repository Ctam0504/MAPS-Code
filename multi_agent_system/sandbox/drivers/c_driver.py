"""
multi_agent_system.sandbox.drivers.c_driver
==========================================
Driver thực thi đa tệp dành cho ngôn ngữ C.
Hỗ trợ biên dịch đồng thời tất cả các file .c và liên kết các file header .h.
"""

import os
import re
import glob
import sys
from typing import Dict
from .base import BaseMultiFileDriver

class CMultiFileDriver(BaseMultiFileDriver):
    def prepare_workspace(
        self, 
        files: Dict[str, str], 
        test_cases: str, 
        host_dir: str, 
        use_docker: bool = False
    ) -> str:
        # 1. Ghi toàn bộ các file .c và .h theo relative path
        self.write_files(files, host_dir)

        # HƯỚNG 3: Sao chép framework minunit.h vào host_dir (chuẩn hóa tương tự JUnit cho Java)
        import shutil
        framework_c_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frameworks', 'c'))
        minunit_src = os.path.join(framework_c_dir, 'minunit.h')
        if os.path.exists(minunit_src):
            shutil.copyfile(minunit_src, os.path.join(host_dir, 'minunit.h'))

        # 2. Tìm tất cả các file header để tự động thêm include
        header_files = [f for f in files.keys() if f.endswith('.h')]
        include_headers = '\n'.join([f'#include "{h}"' for h in header_files])

        cleaned_test = test_cases.strip()

        has_minunit = 'minunit.h' in cleaned_test or 'MU_TEST' in cleaned_test or 'MU_RUN_SUITE' in cleaned_test
        has_main = bool(re.search(r'\bint\s+main\s*\(', cleaned_test) or re.search(r'\bvoid\s+main\s*\(', cleaned_test))

        if has_minunit:
            # Định dạng MinUnit chuẩn hóa
            minunit_prelude = '#define MINUNIT_IMPLEMENTATION\n#include "minunit.h"\n#include <string.h>\n'
            if 'MINUNIT_IMPLEMENTATION' not in cleaned_test:
                cleaned_test = minunit_prelude + cleaned_test
            if include_headers and not any((h in cleaned_test or os.path.basename(h) in cleaned_test) for h in header_files):
                final_code = f"{include_headers}\n\n{cleaned_test}"
            else:
                final_code = cleaned_test
        elif has_main:
            if include_headers and not any((h in cleaned_test or os.path.basename(h) in cleaned_test) for h in header_files):
                final_code = f"#include <stdio.h>\n#include <stdlib.h>\n#include <assert.h>\n#include <string.h>\n{include_headers}\n\n{cleaned_test}\n"
            else:
                final_code = cleaned_test
        else:
            # Tester chỉ viết các câu lệnh assert tự do
            preproc_lines = []
            body_lines = []
            for line in cleaned_test.splitlines():
                stripped = line.strip()
                if stripped.startswith('#include') or stripped.startswith('#define'):
                    preproc_lines.append(stripped)
                else:
                    body_lines.append(line)

            extra_preproc = '\n'.join(preproc_lines)
            body_code = '\n'.join(body_lines)
            final_code = f"#include <stdio.h>\n#include <stdlib.h>\n#include <assert.h>\n#include <string.h>\n{include_headers}\n{extra_preproc}\n\nint main() {{\n    printf(\"[TEST HARNESS] Starting C multi-file verification...\\n\");\n    {body_code}\n    printf(\"\\n[SUCCESS] ALL TEST CASES PASSED\\n\");\n    return 0;\n}}\n"

        harness_path = os.path.join(host_dir, "test_harness.c")
        with open(harness_path, "w", encoding="utf-8") as f:
            f.write(final_code)

        # 3. Phân tách danh sách file mã nguồn dự án (Coder) và file test_harness.c (Tester)
        # Thực hiện cơ chế kiểm thử 2 giai đoạn (2-Phase Verification):
        # Giai đoạn 1: Biên dịch kiểm tra cú pháp toàn bộ file .c dự án với `gcc -c`. Nếu lỗi -> 100% Coder/Planner.
        # Giai đoạn 2: Chỉ khi mã nguồn biên dịch thành công mới biên dịch test_harness.c, liên kết và chạy.
        c_files = glob.glob(os.path.join(host_dir, "**", "*.c"), recursive=True)
        harness_abs = os.path.abspath(harness_path)
        project_c_files = [cf for cf in c_files if os.path.abspath(cf) != harness_abs]

        def has_main_func(filepath: str) -> bool:
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    return bool(re.search(r"\b(int|void)\s+main\s*\(", content))
            except Exception:
                return False

        # Các file dự án không chứa main() sẽ được link cùng test_harness.c (tránh trùng lặp main)
        linkable_project_c_files = [cf for cf in project_c_files if not has_main_func(cf)]

        exe_name = "runner.exe" if sys.platform.startswith("win") else "./runner"
        runner_cmd = "runner.exe" if sys.platform.startswith("win") else "./runner"

        # FIX 3: Thu thập tất cả thư mục con chứa header để thêm vào -I flags
        include_dirs = set()
        for h in header_files:
            dir_part = os.path.dirname(h)
            if dir_part:
                include_dirs.add(dir_part)
        # Luôn thêm -I. (thư mục gốc). Thêm các thư mục con theo thứ tự ổn định.
        include_flags = " ".join([f'-I"{d}"' for d in sorted(include_dirs)]) + " -I."

        if project_c_files:
            proj_c_str = " ".join([f'"{os.path.relpath(cf, host_dir).replace(chr(92), "/")}"' for cf in project_c_files])
            link_c_str = " ".join([f'"{os.path.relpath(cf, host_dir).replace(chr(92), "/")}"' for cf in linkable_project_c_files])
            link_part = f" {link_c_str}" if link_c_str else ""

            if use_docker:
                return (
                    "sh -c 'gcc -c $(find /workspace -name \"*.c\" ! -name \"test_harness.c\") -I/workspace && "
                    "gcc -O2 /workspace/test_harness.c $(find /workspace -name \"*.c\" ! -name \"test_harness.c\" ! -name \"main.c\") "
                    "-I/workspace -o /workspace/runner && /workspace/runner'"
                )
            # Local execution (Windows / Linux):
            # Thêm cờ -fmax-errors=5 để chặn hiệu ứng dây chuyền, chỉ giữ lại các lỗi gốc đầu tiên giống Java/Python
            # Thêm -Werror=implicit-function-declaration để biến cảnh báo gọi hàm thiếu prototype thành lỗi rõ ràng
            cflags = "-fmax-errors=5 -Werror=implicit-function-declaration"
            return f"gcc -c {cflags} {proj_c_str} {include_flags} && gcc -O2 {cflags} test_harness.c{link_part} {include_flags} -o {exe_name} && {runner_cmd}"
        else:
            cflags = "-fmax-errors=5 -Werror=implicit-function-declaration"
            if use_docker:
                return f"sh -c 'gcc -O2 /workspace/test_harness.c -I/workspace -o /workspace/runner && /workspace/runner'"
            return f"gcc -O2 {cflags} test_harness.c {include_flags} -o {exe_name} && {runner_cmd}"
