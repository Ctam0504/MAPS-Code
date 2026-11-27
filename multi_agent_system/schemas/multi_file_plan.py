from typing import List, Optional
from pydantic import BaseModel, Field, AliasChoices

from .file_spec import FileSpec


class MultiFilePlan(BaseModel):
    target_language: str = Field(default="python")
    architecture_pattern: str = Field(default="Modular Architecture")
    execution_order: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("execution_order", "order", "build_order")
    )
    files: List[FileSpec] = Field(default_factory=list)
    rationale: Optional[str] = Field(default="")
