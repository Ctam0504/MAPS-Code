from enum import Enum


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
