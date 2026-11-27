from typing import Dict
from pydantic import BaseModel, Field


class ExecutionRequest(BaseModel):
    language: str = Field(..., description="Ngôn ngữ lập trình: 'python', 'java', 'c'")
    files: Dict[str, str] = Field(..., description="Từ điển các file {filepath_tương_đối: nội_dung_code}")
    test_cases: str = Field(..., description="Mã nguồn kiểm thử hoặc test harness")
    timeout_seconds: float = Field(default=15.0, description="Giới hạn thời gian (giây)")
    memory_limit_mb: int = Field(default=512, description="Giới hạn bộ nhớ RAM (MB)")
