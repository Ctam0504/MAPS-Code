"""
multi_agent_system.sandbox.drivers.java_driver
=============================================
JUnit 5 test driver for multi-file Java projects.
"""

import os
import shutil
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

        framework_dir = os.path.join(host_dir, ".junit")
        classes_dir = os.path.join(host_dir, "classes")
        os.makedirs(framework_dir, exist_ok=True)
        os.makedirs(classes_dir, exist_ok=True)

        framework_root = os.path.join(os.path.dirname(__file__), "..", "frameworks", "junit")
        framework_jar = "junit-platform-console-standalone-1.11.4.jar"
        shutil.copyfile(
            os.path.join(framework_root, framework_jar),
            os.path.join(framework_dir, framework_jar)
        )

        harness_path = os.path.join(host_dir, "TestHarness.java")
        with open(harness_path, "w", encoding="utf-8") as harness_file:
            harness_file.write(test_cases.strip() + "\n")

        java_sources = sorted(path for path in files if path.lower().endswith(".java"))
        source_list_path = os.path.join(host_dir, "project_sources.txt")
        with open(source_list_path, "w", encoding="utf-8") as source_list:
            for source_path in java_sources:
                source_list.write(f'"{source_path.replace(chr(92), "/")}"\n')

        if use_docker:
            commands = ["cd /workspace"]
            if java_sources:
                commands.append(
                    "javac -encoding UTF-8 -d /workspace/classes "
                    "-cp /workspace/.junit/" + framework_jar +
                    " @/workspace/project_sources.txt"
                )
            commands.extend([
                "javac -encoding UTF-8 -d /workspace/classes "
                "-cp /workspace/classes:/workspace/.junit/" + framework_jar +
                " /workspace/TestHarness.java",
                "java -jar /workspace/.junit/" + framework_jar +
                " execute --class-path /workspace/classes "
                "--select-class TestHarness --fail-if-no-tests "
                "--disable-banner --details=summary"
            ])
            return "sh -c '" + " && ".join(commands) + "'"

        framework_path = os.path.join(".junit", framework_jar).replace("\\", "/")
        commands = []
        if java_sources:
            commands.append(
                "javac -encoding UTF-8 -d classes "
                f"-cp {framework_path} @project_sources.txt"
            )
        commands.extend([
            "javac -encoding UTF-8 -d classes "
            f"-cp classes{os.pathsep}{framework_path} TestHarness.java",
            f"java -jar {framework_path} execute --class-path classes "
            "--select-class TestHarness --fail-if-no-tests "
            "--disable-banner --details=summary"
        ])
        return " && ".join(commands)
