from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from .review_target import ReviewTarget


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="allow")

    target: ReviewTarget = Field(..., description="Agent chịu trách nhiệm: PLANNER, CODER hoặc TESTER")
    error_category: str = Field(default="LOCAL", description="'GLOBAL', 'LOCAL', 'TESTCASE' hoặc 'NONE'")
    failed_file: Optional[str] = Field(default=None, description="Tên file đơn lẻ có lỗi (giữ lại để tương thích)")
    failed_files: List[str] = Field(default_factory=list, description="Danh sách các file bị phát hiện lỗi")
    root_cause: str = Field(..., description="Nguyên nhân cốt lõi gây ra lỗi")
    instructions: str = Field(..., description="Chỉ thị sửa đổi cụ thể, chi tiết gửi tới Target Agent")
