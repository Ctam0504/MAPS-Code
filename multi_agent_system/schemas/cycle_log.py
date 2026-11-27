from typing import List, Optional
from pydantic import BaseModel

from .execution_status import ExecutionStatus
from .review_target import ReviewTarget


class CycleLog(BaseModel):
    cycle: int
    attempt_time: str
    target_language: str
    plan_summary: List[str]
    execution_status: ExecutionStatus
    review_target: Optional[ReviewTarget] = None
    note: str
    exit_code: Optional[int] = 0
    execution_time_ms: Optional[float] = 0.0
    stdout: Optional[str] = ""
    stderr: Optional[str] = ""
    error_category: Optional[str] = ""
    root_cause: Optional[str] = ""
    instructions: Optional[str] = ""
    auto_fix_note: Optional[str] = ""
    target_files_to_fix: Optional[List[str]] = None
    adjustment_logs: Optional[List[str]] = None
