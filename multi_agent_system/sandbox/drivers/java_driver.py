"""
multi_agent_system.sandbox.drivers.java_driver
=============================================
Driver thực thi đa tệp dành cho ngôn ngữ Java.
Hỗ trợ biên dịch đồng thời tất cả các file trong package và chạy TestHarness.
"""

import os
import glob
from typing import Dict
from .base import BaseMultiFileDriver


class JavaMultiFileDriver(BaseMultiFileDriver):
    def prepare_workspace(
        self,
        files: Dict[str, str],
        test_cases: str,
        host_dir: str,
        use_docker: bool = False
    ) -> str:
        self.write_files(files, host_dir)

        harness_path = os.path.join(host_dir, "TestHarness.java")
        with open(harness_path, "w", encoding="utf-8") as f:
            f.write(test_cases.strip())

        java_files = glob.glob(os.path.join(host_dir, "**", "*.java"), recursive=True)
        harness_abs = os.path.abspath(harness_path)
        project_java_files = [jf for jf in java_files if os.path.abspath(jf) != harness_abs]

        project_sources_file = os.path.join(host_dir, "project_sources.txt")
        with open(project_sources_file, "w", encoding="utf-8") as f:
            for java_file in project_java_files:
                rel_path = os.path.relpath(java_file, host_dir).replace("\\", "/")
                f.write(f'"{rel_path}"\n')

        if project_java_files:
            if use_docker:
                return (
                    "sh -c 'javac -d /workspace @/workspace/project_sources.txt && "
                    "javac -d /workspace -cp /workspace /workspace/TestHarness.java && "
                    "java -cp /workspace TestHarness'"
                )
            return (
                "javac -encoding UTF-8 -d . @project_sources.txt && "
                "javac -encoding UTF-8 -cp . TestHarness.java && "
                "java -Dfile.encoding=UTF-8 -cp . TestHarness"
            )

        if use_docker:
            return (
                "sh -c 'javac -d /workspace /workspace/TestHarness.java && "
                "java -cp /workspace TestHarness'"
            )
        return "javac -cp . TestHarness.java && java -cp . TestHarness"
