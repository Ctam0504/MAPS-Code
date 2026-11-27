from typing import List
from pydantic import BaseModel, Field, AliasChoices


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
