"""
multi_agent_system.tools.language_detector
==========================================
Công cụ nhận diện ngôn ngữ mã nguồn (Python, Java, C) từ thư mục đầu vào.
Kết hợp giữa thư viện Magika và cơ chế phân tích đuôi tệp tin dự phòng (Fallback).
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from ..schemas.language_type import LanguageType

# Cố gắng nạp thư viện Magika (AI-based file type detection)
try:
    from magika import Magika
    _MAGIKA_INSTANCE = Magika()
    HAS_MAGIKA = True
except Exception:
    _MAGIKA_INSTANCE = None
    HAS_MAGIKA = False

# Bảng quy đổi nhãn phát hiện sang LanguageType
MAPPING_MAGIKA = {
    "python": LanguageType.PYTHON,
    "java": LanguageType.JAVA,
    "c": LanguageType.C,
    "c_header": LanguageType.C,
    "cpp": LanguageType.C
}

EXTENSION_MAP = {
    ".py": LanguageType.PYTHON,
    ".java": LanguageType.JAVA,
    ".c": LanguageType.C,
    ".h": LanguageType.C
}

def detect_language_from_files(file_paths: List[str]) -> Tuple[Optional[LanguageType], Dict[str, int]]:
    """
    Xác định ngôn ngữ chiếm ưu thế nhất từ danh sách đường dẫn tệp.
    Trả về (LanguageType, phân bố đếm số file).
    """
    if not file_paths:
        return None, {}

    stats: Dict[LanguageType, int] = {
        LanguageType.PYTHON: 0,
        LanguageType.JAVA: 0,
        LanguageType.C: 0
    }

    for path_str in file_paths:
        p = Path(path_str)
        if not p.is_file():
            continue

        detected_lang: Optional[LanguageType] = None

        # 1. Thử dùng Magika
        if HAS_MAGIKA and _MAGIKA_INSTANCE is not None:
            try:
                res = _MAGIKA_INSTANCE.identify_path(p)
                label = res.output.label.lower()
                detected_lang = MAPPING_MAGIKA.get(label)
            except Exception:
                detected_lang = None

        # 2. Fallback sang đuôi tệp nếu Magika không nhận ra
        if not detected_lang:
            ext = p.suffix.lower()
            detected_lang = EXTENSION_MAP.get(ext)

        if detected_lang:
            stats[detected_lang] += 1

    # Tìm ngôn ngữ có số lượng file nhiều nhất
    ranked = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    best_lang, count = ranked[0]
    
    counts_dict = {k.value: v for k, v in stats.items()}
    if count == 0:
        return None, counts_dict

    return best_lang, counts_dict


def detect_language_from_folder(folder_path: str) -> Tuple[Optional[LanguageType], Dict[str, int]]:
    """
    Quét đệ quy thư mục và xác định ngôn ngữ mã nguồn của thư mục đó.
    """
    if not folder_path or not os.path.exists(folder_path):
        return None, {}

    all_files: List[str] = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            full_p = os.path.join(root, f)
            # Bỏ qua các file ẩn hoặc thư mục ảo
            if not f.startswith("."):
                all_files.append(full_p)

    return detect_language_from_files(all_files)
