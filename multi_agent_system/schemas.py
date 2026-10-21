"""
multi_agent_system.schemas
=========================
Các mô hình cấu trúc dữ liệu chuẩn (Pydantic Models & Enums)
dành cho toàn bộ hệ thống Multi-Agent Code Generation.
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, AliasChoices


# ==============================================================================
# 1. NGÔN NGỮ LẬP TRÌNH ĐƯỢC HỖ TRỢ
# ==============================================================================
class LanguageType(str, Enum):
    PYTHON = "python"
    JAVA = "java"
    C = "c"

    @classmethod
    def from_str(cls, val: str) -> "LanguageType":
        val_clean = val.lower().strip()
        if val_clean in ["python", "py"]:
            return cls.PYTHON
        elif val_clean in ["java"]:
            return cls.JAVA
        elif val_clean in ["c", "cpp", "c++", "h"]:
            return cls.C
        raise ValueError(f"Ngôn ngữ '{val}' không được hỗ trợ. Chỉ hỗ trợ: python, java, c.")

# ==============================================================================
# 2. SCHEMA KẾ HOẠCH ĐA TỆP (PLANNER -> CODER)
# ==============================================================================


class FileSpec(BaseModel):
    filepath: str = Field(..., description="Đường dẫn file")
    action: str = Field(default="CREATE", description="CREATE / MODIFY / KEEP")
    dependencies: List[str] = Field(default_factory=list)
    external_dependencies: List[str] = Field(default_factory=list)
    purpose: str = Field(
        default="Triển khai logic module",
        validation_alias=AliasChoices("purpose", "description", "summary")
    )
    interface_summary: str = Field(
        default="",
        validation_alias=AliasChoices("interface_summary", "interfaces", "interface", "signatures")
    )

class MultiFilePlan(BaseModel):
    target_language: str = Field(default="python")
    architecture_pattern: str = Field(default="Modular Architecture")
    execution_order: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("execution_order", "order", "build_order")
    )
    files: List[FileSpec] = Field(default_factory=list)
    rationale: Optional[str] = Field(default="")

# ==============================================================================
# 3. SCHEMA THỰC THI KIỂM THỬ (SANDBOX ENGINE)
# ==============================================================================
class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"                         # Chạy thành công, pass toàn bộ test
    FAILED = "FAILED"                           # Thực thi thất bại (exit_code != 0)
    COMPILATION_ERROR = "COMPILATION_ERROR"     # Giữ lại để tương thích ngược
    RUNTIME_ERROR = "RUNTIME_ERROR"             # Giữ lại để tương thích ngược
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED" # Quá thời gian timeout
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED" # Vượt quá dung lượng RAM
    SYSTEM_ERROR = "SYSTEM_ERROR"               # Lỗi môi trường hệ điều hành

class ExecutionRequest(BaseModel):
    language: str = Field(..., description="Ngôn ngữ lập trình: 'python', 'java', 'c'")
    files: Dict[str, str] = Field(..., description="Từ điển các file {filepath_tương_đối: nội_dung_code}")
    test_cases: str = Field(..., description="Mã nguồn kiểm thử hoặc test harness")
    timeout_seconds: float = Field(default=15.0, description="Giới hạn thời gian (giây)")
    memory_limit_mb: int = Field(default=512, description="Giới hạn bộ nhớ RAM (MB)")

class ExecutionResult(BaseModel):
    status: ExecutionStatus
    exit_code: int = Field(..., description="Mã thoát (0: thành công, khác 0: lỗi)")
    stdout: str = Field(default="", description="Output chuẩn STDOUT")
    stderr: str = Field(default="", description="Log lỗi chuẩn STDERR")
    execution_time_ms: float = Field(default=0.0, description="Thời gian chạy (ms)")
    memory_used_kb: Optional[int] = Field(default=0, description="Dung lượng RAM tiêu tốn (KB)")

# ==============================================================================
# 4. SCHEMA PHÂN ĐỊNH LỖI (REVIEWER DECISION)
# ==============================================================================
class ReviewTarget(str, Enum):
    PLANNER = "PLANNER"   # Lỗi Global: mâu thuẫn giữa các file, sai interface, sai import
    CODER = "CODER"       # Lỗi Local: cú pháp trong 1 file, lỗi logic cài đặt bên trong hàm
    TESTER = "TESTER"     # Lỗi Testcase: assertion sai so với yêu cầu, giả định sai
    PASSED = "PASSED"     # Đạt yêu cầu, không có lỗi
    UNKNOWN = "UNKNOWN"   # Không xác định

class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = Field(default="REJECTED", description="'PASSED' hoặc 'REJECTED'")
    target: ReviewTarget = Field(..., description="Agent chịu trách nhiệm: PLANNER, CODER, TESTER")
    error_category: str = Field(default="LOCAL", description="'GLOBAL', 'LOCAL', 'TESTCASE' hoặc 'NONE'")
    failed_file: Optional[str] = Field(default=None, description="Tên file đơn lẻ có lỗi (giữ lại để tương thích)")
    failed_files: List[str] = Field(default_factory=list, description="Danh sách các file bị phát hiện lỗi")
    root_cause: str = Field(..., description="Nguyên nhân cốt lõi gây ra lỗi")
    instructions: str = Field(..., description="Chỉ thị sửa đổi cụ thể, chi tiết gửi tới Target Agent")
    audit_table: Optional[Any] = Field(default="", description="Bảng phân tích logic audit (nếu có)")

# ==============================================================================
# 5. SCHEMA NHẬT KÝ VÒNG LẶP (COORDINATOR LOG)
# ==============================================================================
class CycleLog(BaseModel):
    cycle: int
    attempt_time: str
    target_language: str
    plan_summary: List[str]
    execution_status: ExecutionStatus
    review_target: ReviewTarget
    note: str