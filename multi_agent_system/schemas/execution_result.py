from typing import Optional
from pydantic import BaseModel, Field

from .execution_status import ExecutionStatus


class ExecutionResult(BaseModel):
    status: ExecutionStatus
    exit_code: int = Field(..., description="Mã thoát (0: thành công, khác 0: lỗi)")
    stdout: str = Field(default="", description="Output chuẩn STDOUT")
    stderr: str = Field(default="", description="Log lỗi chuẩn STDERR")
    execution_time_ms: float = Field(default=0.0, description="Thời gian chạy (ms)")
    memory_used_kb: Optional[int] = Field(default=0, description="Dung lượng RAM tiêu tốn (KB)")
