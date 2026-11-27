from enum import Enum


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"                         # Chạy thành công, pass toàn bộ test
    FAILED = "FAILED"                           # Thực thi thất bại (exit_code != 0)
    COMPILATION_ERROR = "COMPILATION_ERROR"     # Giữ lại để tương thích ngược
    RUNTIME_ERROR = "RUNTIME_ERROR"             # Giữ lại để tương thích ngược
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED" # Quá thời gian timeout
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED" # Vượt quá dung lượng RAM
    SYSTEM_ERROR = "SYSTEM_ERROR"               # Lỗi môi trường hệ điều hành
