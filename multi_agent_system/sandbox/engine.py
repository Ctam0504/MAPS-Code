"""
multi_agent_system.sandbox.engine
=================================
Sandbox Engine hỗ trợ thực thi mã nguồn đa tệp (Multi-file) cho cả 3 ngôn ngữ: Python, Java, C.
Hỗ trợ 2 chế độ:
1. Local Subprocess Mode (Mặc định): Chạy trực tiếp native trên Windows/Linux mà không cần Docker.
2. Docker Mode: Chạy trong isolated Docker container khi được cấu hình.
"""

import os
import uuid
import time
import shutil
import subprocess
from typing import Optional

from ..schemas import ExecutionRequest, ExecutionResult, ExecutionStatus
from .drivers import MultiFileDriverFactory
from .. import config

try:
    import docker
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False


class MultiFileSandboxEngine:
    def __init__(self, use_docker: Optional[bool] = None, base_image: Optional[str] = None):
        self.use_docker = use_docker if use_docker is not None else config.SANDBOX_USE_DOCKER
        self.custom_base_image = base_image is not None
        self.base_image = base_image or config.SANDBOX_DOCKER_BASE_IMAGE
        self.client = None

        if self.use_docker:
            if not HAS_DOCKER:
                raise ImportError("Thư viện 'docker' chưa được cài đặt. Vui lòng cài đặt qua pip install docker.")
            try:
                self.client = docker.from_env()
                self.client.ping()
            except Exception as e:
                print(f"⚠️ [Sandbox Engine] Không thể kết nối tới Docker Daemon: {e}. Tự động chuyển sang chế độ Local Subprocess.")
                self.use_docker = False

    def execute(self, req: ExecutionRequest) -> ExecutionResult:
        driver = MultiFileDriverFactory.get_driver(req.language)

        # Tạo thư mục làm việc tạm thời cho phiên thực thi này
        session_id = f"sandbox_run_{uuid.uuid4().hex[:8]}"
        base_temp_dir = config.DEFAULT_TEMP_SANDBOX_DIR
        os.makedirs(base_temp_dir, exist_ok=True)
        host_dir = os.path.abspath(os.path.join(base_temp_dir, session_id))
        os.makedirs(host_dir, exist_ok=True)

        try:
            exec_cmd = driver.prepare_workspace(
                files=req.files, 
                test_cases=req.test_cases, 
                host_dir=host_dir, 
                use_docker=self.use_docker
            )
            start_time = time.perf_counter()

            if self.use_docker and self.client is not None:
                return self._execute_docker(req, exec_cmd, host_dir, start_time)
            else:
                return self._execute_local(req, exec_cmd, host_dir, start_time)

        finally:
            # Dọn dẹp thư mục tạm sau khi kết thúc
            if os.path.exists(host_dir):
                shutil.rmtree(host_dir, ignore_errors=True)

    def _execute_docker(
        self, 
        req: ExecutionRequest, 
        exec_cmd: str, 
        host_dir: str, 
        start_time: float
    ) -> ExecutionResult:
        try:
            image = self.base_image
            if req.language.lower().strip() == "java" and not self.custom_base_image:
                image = config.SANDBOX_DOCKER_JAVA_IMAGE
            container = self.client.containers.run(
                image=image,
                command=exec_cmd,
                volumes={host_dir: {'bind': '/workspace', 'mode': 'rw'}},
                network_mode="none",
                mem_limit=f"{req.memory_limit_mb}m",
                memswap_limit=f"{req.memory_limit_mb}m",
                pids_limit=64,
                cap_drop=["ALL"],
                detach=True
            )

            try:
                exit_res = container.wait(timeout=int(req.timeout_seconds))
                exec_time_ms = (time.perf_counter() - start_time) * 1000

                exit_code = exit_res.get("StatusCode", -1)
                stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="ignore")
                stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="ignore")

                status = self._parse_status(exit_code, stderr, stdout)

                return ExecutionResult(
                    status=status,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    execution_time_ms=round(exec_time_ms, 2)
                )
            except Exception:
                try:
                    container.kill()
                except Exception:
                    pass
                return ExecutionResult(
                    status=ExecutionStatus.TIME_LIMIT_EXCEEDED,
                    exit_code=124,
                    stdout="",
                    stderr=f"Quá thời gian thực thi cho phép ({req.timeout_seconds}s)",
                    execution_time_ms=req.timeout_seconds * 1000
                )
            finally:
                container.remove(force=True)

        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.SYSTEM_ERROR,
                exit_code=-1,
                stdout="",
                stderr=f"Docker Container Error: {str(e)}",
                execution_time_ms=0
            )

    def _execute_local(
        self, 
        req: ExecutionRequest, 
        exec_cmd: str, 
        host_dir: str, 
        start_time: float
    ) -> ExecutionResult:
        try:
            process = subprocess.Popen(
                exec_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=host_dir,
                text=True
            )

            try:
                stdout, stderr = process.communicate(timeout=req.timeout_seconds)
                exec_time_ms = (time.perf_counter() - start_time) * 1000
                exit_code = process.returncode

                status = self._parse_status(exit_code, stderr, stdout)

                return ExecutionResult(
                    status=status,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    execution_time_ms=round(exec_time_ms, 2)
                )

            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return ExecutionResult(
                    status=ExecutionStatus.TIME_LIMIT_EXCEEDED,
                    exit_code=124,
                    stdout=stdout,
                    stderr=f"Quá thời gian thực thi ({req.timeout_seconds}s)",
                    execution_time_ms=req.timeout_seconds * 1000
                )

        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.SYSTEM_ERROR,
                exit_code=-1,
                stdout="",
                stderr=f"Local Execution Error: {str(e)}",
                execution_time_ms=0
            )

    @staticmethod
    def _parse_status(exit_code: int, stderr: str, stdout: str) -> ExecutionStatus:
        """
        Xác định trạng thái thực thi khách quan:
        - exit_code == 0: SUCCESS (vượt qua toàn bộ kiểm thử)
        - exit_code != 0: FAILED (thất bại).
        Toàn bộ raw syntax/output lỗi (stderr, stdout) được giữ nguyên vẹn
        để Reviewer tự đọc và phân tích bản chất lỗi mà không bị gán nhãn phỏng đoán.
        """
        if exit_code == 0:
            return ExecutionStatus.SUCCESS
        return ExecutionStatus.FAILED
