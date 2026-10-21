"""
multi_agent_system.coordinator
==============================
Bộ điều phối toàn bộ chu trình Multi-Agent Code Generation và Vòng lặp Tự sửa lỗi (Self-Correction Loop).
Quản lý luồng tương tác giữa:
Planner -> Coder -> Tester -> Sandbox -> Reviewer -> Tự sửa lỗi theo phân định (Global / Local / Testcase).
"""

import os
import time
import datetime
from typing import Dict, Optional, Any, List

from multi_agent_system.schemas import (
    MultiFilePlan,
    FileSpec,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ReviewDecision,
    ReviewTarget,
    CycleLog,
)
from multi_agent_system.agents import (
    PlannerAgent,
    CoderAgent,
    TesterAgent,
    ReviewerAgent,
)
from multi_agent_system.sandbox import MultiFileSandboxEngine
from multi_agent_system.memory import SharedMemory
import multi_agent_system.config as config

class MultiAgentCoordinator:
    def __init__(
        self,
        output_dir: Optional[str] = None,
        max_cycles: Optional[int] = None,
        use_docker: Optional[bool] = None,
        enable_shared_memory: Optional[bool] = None,
        enabled_agents: Optional[List[str]] = None
    ):
        self.output_dir = os.path.abspath(output_dir or config.DEFAULT_OUTPUT_DIR)
        self.max_cycles = max_cycles if max_cycles is not None else config.MAX_SELF_CORRECTION_CYCLES
        self.use_docker = use_docker if use_docker is not None else config.SANDBOX_USE_DOCKER
        self.enable_shared_memory = (
            enable_shared_memory if enable_shared_memory is not None else getattr(config, "ENABLE_SHARED_MEMORY", True)
        )
        configured_agents = enabled_agents if enabled_agents is not None else config.ENABLED_AGENTS
        self.enabled_agents = {agent.lower().strip() for agent in configured_agents}
        self.enabled_agents.add("coder")

        # Khởi tạo các Agent và Sandbox Engine
        self.planner = PlannerAgent()
        self.coder = CoderAgent()
        self.tester = TesterAgent()
        self.reviewer = ReviewerAgent()
        self.sandbox = MultiFileSandboxEngine(use_docker=self.use_docker)

        # Shared Memory giữa các Agent
        self.memory = SharedMemory(enabled=self.enable_shared_memory)

        # Trạng thái điều phối
        self.current_plan: Optional[MultiFilePlan] = None
        self.initial_files: Dict[str, str] = {}
        self.current_files: Dict[str, str] = {}
        self.current_tests: str = ""
        self.cycle_logs: List[CycleLog] = []

    def _build_fallback_plan(
        self,
        task_prompt: str,
        target_language: Optional[str],
    ) -> MultiFilePlan:
        """Build a minimal plan for variants that intentionally disable Planner."""
        lang = target_language or config.DEFAULT_TARGET_LANGUAGE
        files = [
            FileSpec(
                filepath=filepath,
                action="MODIFY",
                purpose="Benchmark target file supplied as existing context.",
                interface_summary=f"Preserve the existing file contract and satisfy: {task_prompt}",
            )
            for filepath in self.initial_files
        ]
        if not files:
            files = [
                FileSpec(
                    filepath=f"main.{ 'py' if lang == 'python' else ('java' if lang == 'java' else 'c')}",
                    action="CREATE",
                    purpose="Benchmark target implementation.",
                    interface_summary=task_prompt,
                )
            ]
        return MultiFilePlan(
            target_language=lang,
            architecture_pattern="Benchmark fallback plan (Planner disabled)",
            execution_order=[file.filepath for file in files],
            files=files,
            rationale="Planner disabled by benchmark variant; coordinator supplied the minimal contract.",
        )

    def _load_input_folder(self, input_folder: str) -> Dict[str, str]:
        """
        Nạp toàn bộ mã nguồn và cấu trúc tệp tin từ thư mục tiền sắp xếp của người dùng.
        """
        loaded_files: Dict[str, str] = {}
        if not input_folder or not os.path.exists(input_folder):
            return loaded_files

        for root, _, files in os.walk(input_folder):
            for f in files:
                if f.startswith("."):
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext in [".py", ".java", ".c", ".h", ".cpp"]:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, input_folder).replace("\\", "/")
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as fp:
                            loaded_files[rel_p] = fp.read()
                    except Exception as e:
                        print(f"⚠️ Không thể đọc file '{rel_p}': {e}")
        return loaded_files

    def _save_files_to_output(self, files: Dict[str, str], test_harness: str, lang: str):
        """Lưu toàn bộ các tệp mã nguồn và test harness vào thư mục output_dir."""
        os.makedirs(self.output_dir, exist_ok=True)
        for rel_p, content in files.items():
            full_p = os.path.join(self.output_dir, rel_p.lstrip("/\\"))
            os.makedirs(os.path.dirname(full_p), exist_ok=True)
            with open(full_p, "w", encoding="utf-8") as f:
                f.write(content)

        # Lưu file testcase
        test_filename = "TestHarness.java" if lang.lower() == "java" else (
            f"test_harness.{'py' if lang.lower() == 'python' else 'c'}"
        )
        test_full_p = os.path.join(self.output_dir, test_filename)
        with open(test_full_p, "w", encoding="utf-8") as f:
            f.write(test_harness)

    def _generate_markdown_report(self, task_prompt: str, success: bool, total_time: float) -> str:
        """Tạo báo cáo chi tiết Markdown tổng kết quá trình sinh mã nguồn và tự sửa lỗi."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        table_rows = ""
        for log in self.cycle_logs:
            table_rows += (
                f"| {log.cycle} | {log.target_language.upper()} "
                f"| {log.execution_status.value} | {log.review_target.value} "
                f"| {log.note.replace(chr(10), ' ')} |\n"
            )

        files_list_md = ""
        for fp, code in self.current_files.items():
            files_list_md += f"### Tệp `{fp}`\n```{self.current_plan.target_language if self.current_plan else ''}\n{code}\n```\n\n"

        report = f"""# 📊 BÁO CÁO HỆ THỐNG MULTI-AGENT CODE GENERATION ĐA TỆP

- **Thời gian thực hiện:** {timestamp}
- **Yêu cầu bài toán:** {task_prompt}
- **Ngôn ngữ đích:** {self.current_plan.target_language.upper() if self.current_plan else 'N/A'}
- **Mẫu kiến trúc:** {self.current_plan.architecture_pattern if self.current_plan else 'N/A'}
- **Kết quả cuối cùng:** {"✅ THÀNH CÔNG" if success else "❌ THẤT BẠI (ĐẠT NGƯỠNG TỐI ĐA)"}
- **Tổng thời gian xử lý:** {total_time:.2f} giây
- **Số chu trình tự sửa lỗi:** {len(self.cycle_logs)} / {self.max_cycles}

---

## 📈 Nhật ký các vòng lặp tự sửa lỗi (Self-Correction Cycles)

| Vòng (Cycle) | Ngôn ngữ | Trạng thái Sandbox | Đối tượng sai (Reviewer) | Ghi chú chi tiết |
| :---: | :---: | :---: | :---: | :--- |
{table_rows}

---

## 📁 Cấu trúc và Mã nguồn các tệp đã sinh

{files_list_md}

## 🧪 Kịch bản kiểm thử (Test Harness)
```{self.current_plan.target_language if self.current_plan else ''}
{self.current_tests}
```
"""
        report_path = os.path.join(self.output_dir, "generation_report.md")
        os.makedirs(self.output_dir, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        return report_path

    async def run(
        self,
        task_prompt: str,
        input_folder: Optional[str] = None,
        target_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Thực thi toàn bộ luồng:
        Planner -> Coder -> Tester -> Sandbox -> (Reviewer Loop nếu có lỗi).
        """
        start_time = time.time()
        print("\n" + "═" * 70)
        print("🚀 BẮT ĐẦU QUY TRÌNH MULTI-AGENT CODE GENERATION ĐA TỆP")
        print("═" * 70)

        # ----------------------------------------------------------------------
        # BƯỚC 0: NẠP VÀ KIỂM TRA FOLDER INPUT TIỀN SẮP XẾP
        # ----------------------------------------------------------------------
        self.initial_files = {}
        if input_folder and os.path.exists(input_folder):
            self.initial_files = self._load_input_folder(input_folder)
            if self.initial_files:
                print(f"\n📂 [BƯỚC 0] Đã nạp thành công {len(self.initial_files)} tệp từ folder input tiền sắp xếp:")
                for fp in self.initial_files.keys():
                    print(f"   * {fp}")
            else:
                print(f"\n📂 [BƯỚC 0] Thư mục input '{input_folder}' hiện đang rỗng.")

        # ----------------------------------------------------------------------
        # BƯỚC 1: PLANNER LẬP KẾ HOẠCH KIẾN TRÚC BAN ĐẦU
        # ----------------------------------------------------------------------
        self.memory.set_task_goal(task_prompt)
        if "planner" in self.enabled_agents:
            print(f"\n📐 [BƯỚC 1] Khởi chạy Planner Agent (Shared Memory: {'BẬT' if self.enable_shared_memory else 'TẮT'})...")
            self.current_plan = await self.planner.plan_codebase(
                task_prompt=task_prompt,
                input_folder=input_folder,
                target_language=target_language
            )
        else:
            print("\n📐 [BƯỚC 1] Planner Agent bị tắt theo Variant; dùng fallback plan...")
            self.current_plan = self._build_fallback_plan(task_prompt, target_language)
        self.memory.update_plan(self.current_plan)
        lang = self.current_plan.target_language
        print(f"   -> Ngôn ngữ đích xác định: {lang.upper()}")
        print(f"   -> Mẫu kiến trúc: {self.current_plan.architecture_pattern}")
        print(f"   -> Thứ tự sinh file Topo: {self.current_plan.execution_order}")
        print("   -> Chi tiết FileSpec:")
        for file_spec in self.current_plan.files:
            print(f"      [FileSpec] {file_spec.filepath}")
            print(f"         action: {file_spec.action}")
            print(f"         dependencies: {file_spec.dependencies}")
            print(f"         external_dependencies: {file_spec.external_dependencies}")
            print(f"         purpose: {file_spec.purpose}")
            print(f"         interface_summary: {file_spec.interface_summary}")

        # ----------------------------------------------------------------------
        # BƯỚC 2: CODER SINH MÃ NGUỒN CÁC TỆP ĐẦU TIÊN
        # ----------------------------------------------------------------------
        print(f"\n💻 [BƯỚC 2] Khởi chạy Coder Agent sinh mã nguồn ({lang.upper()})...")
        self.current_files = self.coder.generate_all_files(
            plan=self.current_plan,
            task_goal=task_prompt,
            initial_files=self.initial_files,
            output_dir=self.output_dir,
            shared_memory=self.memory
        )
        self.memory.update_files(self.current_files)

        # ----------------------------------------------------------------------
        # BƯỚC 3: TESTER SINH KỊCH BẢN KIỂM THỬ BAN ĐẦU
        # ----------------------------------------------------------------------
        if "tester" in self.enabled_agents:
            print("\n🧪 [BƯỚC 3] Khởi chạy Tester Agent sinh Test Harness...")
            tester_input_files = self.memory.get_tester_files(self.current_files)
            self.current_tests = self.tester.generate_tests(
                task_goal=task_prompt,
                files_dict=tester_input_files,
                target_language=lang
            )
        else:
            print("\n🧪 [BƯỚC 3] Tester Agent bị tắt theo Variant; bỏ qua Test Harness...")
            self.current_tests = ""
        self.memory.update_tests(self.current_tests)

        # ----------------------------------------------------------------------
        # BƯỚC 4: VÒNG LẶP KIỂM THỬ VÀ TỰ SỬA LỖI (SELF-CORRECTION LOOP)
        # ----------------------------------------------------------------------
        success = False

        for cycle in range(1, self.max_cycles + 1):
            print(f"\n{'─' * 25} VÒNG TỰ SỬA LỖI {cycle}/{self.max_cycles} {'─' * 25}")
            
            # 4.1 Thực thi mã nguồn trong Sandbox Engine
            print(f"⚙️ [Sandbox] Đang thực thi kiểm thử đa tệp ({'Docker' if self.use_docker else 'Local Subprocess'})...")
            req = ExecutionRequest(
                language=lang,
                files=self.current_files,
                test_cases=self.current_tests,
                timeout_seconds=config.SANDBOX_TIMEOUT_SECONDS,
                memory_limit_mb=config.SANDBOX_MEMORY_LIMIT_MB
            )
            exec_res = self.sandbox.execute(req)

            print(f"   -> Trạng thái: {exec_res.status.value} (Mã thoát: {exec_res.exit_code}, Thời gian: {exec_res.execution_time_ms} ms)")
            if exec_res.stdout:
                print(f"   -> STDOUT: {exec_res.stdout.strip()}...")
            if exec_res.stderr:
                print(f"   -> STDERR: {exec_res.stderr.strip()}...")

            # 4.2 Kiểm tra nếu thành công
            if exec_res.status == ExecutionStatus.SUCCESS:
                print(f"\n🎉 [THÀNH CÔNG] Toàn bộ mã nguồn đã vượt qua kiểm thử tại Vòng {cycle}!")
                self.cycle_logs.append(CycleLog(
                    cycle=cycle,
                    attempt_time=datetime.datetime.now().strftime("%H:%M:%S"),
                    target_language=lang,
                    plan_summary=[f.filepath for f in self.current_plan.files],
                    execution_status=exec_res.status,
                    review_target=ReviewTarget.PASSED,
                    note="Vượt qua toàn bộ kiểm thử trong Sandbox thành công."
                ))
                success = True
                break

            # 4.3 Nếu có lỗi: Gửi log lỗi cho Reviewer Agent thẩm định
            if "reviewer" not in self.enabled_agents:
                print("\n❌ [KẾT QUẢ] Sandbox thất bại; Reviewer Agent bị tắt nên dừng workflow.")
                self.cycle_logs.append(CycleLog(
                    cycle=cycle,
                    attempt_time=datetime.datetime.now().strftime("%H:%M:%S"),
                    target_language=lang,
                    plan_summary=[f.filepath for f in self.current_plan.files],
                    execution_status=exec_res.status,
                    review_target=ReviewTarget.UNKNOWN,
                    note="Sandbox thất bại và Reviewer bị tắt theo Variant."
                ))
                break

            print(f"\n⚖️ [Reviewer] Thẩm định lỗi và phân định trách nhiệm...")
            err_details = f"Exit Code: {exec_res.exit_code}\nSTDERR:\n{exec_res.stderr}\nSTDOUT:\n{exec_res.stdout}"
            decision = self.reviewer.review(
                task_goal=task_prompt,
                plan=self.current_plan,
                files_dict=self.current_files,
                test_cases=self.current_tests,
                error_msg=err_details,
                workspace_dir=self.output_dir
            )

            print(f"   -> Đối tượng sai: {decision.target.value} (Phân loại: {decision.error_category})")
            print(f"   -> Nguyên nhân: {decision.root_cause}")
            print(f"   -> Chỉ thị sửa đổi: {decision.instructions}")

            self.cycle_logs.append(CycleLog(
                cycle=cycle,
                attempt_time=datetime.datetime.now().strftime("%H:%M:%S"),
                target_language=lang,
                plan_summary=[f.filepath for f in self.current_plan.files],
                execution_status=exec_res.status,
                review_target=decision.target,
                note=f"[{decision.error_category}] {decision.root_cause}"
            ))

            feedback_entry = f"\n[VÒNG {cycle} - LỖI {decision.target.value}]: {decision.instructions}\n"

        # 4.4 Thực hiện sửa đổi dựa theo phán quyết của Reviewer
            
            # --- [BỔ SUNG 1] TỰ ĐỘNG CHUẨN HÓA VAI TRÒ (ROLE AUTO-CORRECTION) ---
            # Tránh tình trạng Reviewer phán nhầm Coder/Tester
            combined_text = f"{decision.root_cause} {decision.instructions} {err_details}"
            
            if decision.target == ReviewTarget.CODER:
                # Nếu Reviewer bảo Coder nhưng lại yêu cầu sửa test_harness -> Chuyển sang TESTER
                if "test_harness" in combined_text.lower() and not any(fp in combined_text for fp in self.current_files.keys()):
                    print("   🔄 [Coordinator Auto-Fix] Phát hiện lỗi thuộc test_harness. Chuyển quyền sửa cho TESTER.")
                    decision.target = ReviewTarget.TESTER
            elif decision.target == ReviewTarget.TESTER:
                # Nếu Reviewer bảo Tester nhưng hướng dẫn sửa file mã nguồn (.c/.h) -> Chuyển sang CODER
                src_mentioned = [fp for fp in self.current_files.keys() if fp in combined_text]
                if src_mentioned and "test_harness" not in decision.instructions.lower():
                    print(f"   🔄 [Coordinator Auto-Fix] Phát hiện chỉ thị sửa file nguồn {src_mentioned}. Chuyển quyền sửa cho CODER.")
                    decision.target = ReviewTarget.CODER

            if decision.target == ReviewTarget.PLANNER and "planner" in self.enabled_agents:
                print("   🛠️ [Điều chỉnh] Planner Agent đang tái cấu trúc kế hoạch kiến trúc...")
                self.current_plan = await self.planner.refine_plan(
                    task_prompt=task_prompt,
                    current_plan=self.current_plan,
                    reviewer_instructions=decision.instructions,
                    error_log=err_details,
                    current_folder=self.output_dir
                )
                self.memory.update_plan(self.current_plan)
                for file_spec in self.current_plan.files:
                            print(f"      [FileSpec] {file_spec.filepath}")
                            print(f"         action: {file_spec.action}")
                            print(f"         dependencies: {file_spec.dependencies}")
                            print(f"         external_dependencies: {file_spec.external_dependencies}")
                            print(f"         purpose: {file_spec.purpose}")
                            print(f"         interface_summary: {file_spec.interface_summary}")
                print("   🛠️ [Điều chỉnh] Coder Agent đồng bộ lại các file mã nguồn...")
                self.current_files = self.coder.generate_all_files(
                    plan=self.current_plan,
                    task_goal=task_prompt,
                    initial_files=self.current_files,
                    output_dir=self.output_dir,
                    shared_memory=self.memory,
                    feedback=f"{decision.root_cause}\n{decision.instructions}"
                )
                self.memory.update_files(self.current_files)

            elif decision.target == ReviewTarget.CODER:
                target_files_to_fix: List[str] = []

                # (1) ƯU TIÊN 1: Lấy từ failed_files do Reviewer trả về
                reviewer_failed_files = getattr(decision, "failed_files", []) or []
                if not reviewer_failed_files and getattr(decision, "failed_file", None):
                    reviewer_failed_files = [decision.failed_file]

                for rf in reviewer_failed_files:
                    clean_rf = os.path.basename(str(rf).strip().strip("`'\""))
                    for fp in self.current_files.keys():
                        if fp == rf or os.path.basename(fp) == clean_rf:
                            if fp not in target_files_to_fix:
                                target_files_to_fix.append(fp)

                # (2) ƯU TIÊN 2: Quét tên file xuất hiện trong root_cause & instructions của Reviewer
                text_to_search = f"{decision.root_cause} {decision.instructions}"
                for fp in self.current_files.keys():
                    base_name = os.path.basename(fp)
                    if base_name in text_to_search or fp in text_to_search:
                        if fp not in target_files_to_fix:
                            target_files_to_fix.append(fp)

                # (3) ƯU TIÊN 3: Quét tên hàm (Function-level Trace)
                # Nếu Reviewer nhắc tới hàm nào (vd: load_from_file), tìm xem hàm đó nằm trong file nào!
                import re
                words = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{3,}', text_to_search))
                for word in words:
                    for fp, code in self.current_files.items():
                        if fp.endswith(".c") and f"{word}(" in code:
                            if fp not in target_files_to_fix and fp not in ["main.c"]:
                                target_files_to_fix.append(fp)

                # (4) FALLBACK 4: Quét compiler log trong err_details
                if not target_files_to_fix:
                    for fp in self.current_files.keys():
                        base_name = os.path.basename(fp)
                        if base_name in err_details:
                            if fp not in target_files_to_fix:
                                target_files_to_fix.append(fp)

                # (5) FALLBACK CUỐI CÙNG: Không còn đường nào mới chọn file có chứa logic chính (không mặc định main.c)
                if not target_files_to_fix:
                    # Ưu tiên các file .c khác trước main.c
                    c_files = [f for f in self.current_files.keys() if f.endswith('.c') and f != 'main.c']
                    target_files_to_fix = [c_files[0]] if c_files else [self.current_plan.execution_order[-1]]

                print(f"   📋 [Coordinator] Danh sách tệp cần Coder sửa: {target_files_to_fix}")

                for target_file in target_files_to_fix:
                    print(f"   🛠️ [Điều chỉnh] Coder Agent đang sửa lỗi trong file: `{target_file}`...")
                    coder_all_files = self.current_files if self.enable_shared_memory else {target_file: self.current_files[target_file]}
                    old_code = self.current_files[target_file]
                    fixed_code = self.coder.fix_file(
                        filepath=target_file,
                        current_code=old_code,
                        all_files=coder_all_files,
                        reviewer_instructions=decision.instructions,
                        error_log=err_details,
                        target_language=lang,
                        task_goal=task_prompt
                    )
                    if fixed_code.strip() == old_code.strip():
                        print(f"   ⚠️ [Coder Warning] Mã nguồn tệp `{target_file}` không có sự thay đổi sau khi sửa!")
                    else:
                        print(f"   ✅ [Coder] Đã áp dụng các thay đổi mới vào `{target_file}`.")
                    self.current_files[target_file] = fixed_code
                    self.memory.update_file(target_file, fixed_code)
                    if self.output_dir:
                        full_p = os.path.join(self.output_dir, target_file.lstrip("/\\"))
                        os.makedirs(os.path.dirname(full_p), exist_ok=True)
                        with open(full_p, "w", encoding="utf-8") as f:
                            f.write(fixed_code)

            elif decision.target == ReviewTarget.TESTER and "tester" in self.enabled_agents:
                print("   🛠️ [Điều chỉnh] Tester Agent đang sửa lại kịch bản kiểm thử...")
                tester_fix_files = self.memory.get_tester_files(self.current_files)
                self.current_tests = self.tester.fix_tests(
                    task_goal=task_prompt,
                    files_dict=tester_fix_files,
                    current_tests=self.current_tests,
                    target_language=lang,
                    reviewer_instructions=decision.instructions,
                    error_log=err_details
                )
                self.memory.update_tests(self.current_tests)

        total_elapsed = time.time() - start_time

        # ----------------------------------------------------------------------
        # BƯỚC 5: LƯU TRỮ KẾT QUẢ VÀ TẠO BÁO CÁO TỔNG KẾT
        # ----------------------------------------------------------------------
        print("\n" + "═" * 70)
        print("💾 [HOÀN TẤT] Lưu trữ mã nguồn và tạo báo cáo tổng kết...")
        self._save_files_to_output(self.current_files, self.current_tests, lang)
        report_file = self._generate_markdown_report(task_prompt, success, total_elapsed)

        print(f"📁 Mã nguồn các tệp đã được lưu tại: {self.output_dir}")
        print(f"📊 Báo cáo nghiên cứu chi tiết đã lưu tại: {report_file}")
        print("═" * 70 + "\n")

        return {
            "success": success,
            "target_language": lang,
            "total_cycles": len(self.cycle_logs),
            "execution_time_seconds": round(total_elapsed, 2),
            "files": self.current_files,
            "output_directory": self.output_dir,
            "report_path": report_file
        }
