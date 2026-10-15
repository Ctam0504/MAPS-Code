"""
multi_agent_system.config
========================
Tập trung toàn bộ các tham số cấu hình hệ thống Multi-Agent Code Generation:
- Số lượng và vai trò các Agent
- Số vòng lặp tự sửa lỗi (Self-Correction Cycles)
- Tùy chọn model LLM cho từng Agent
- Cấu hình Sandbox Engine (Local/Docker, timeout, memory)
- Cấu hình GraphRAG và Language Detector
"""

import os
from typing import List, Dict, Any

# ==============================================================================
# 1. CẤU HÌNH KẾT NỐI OLLAMA / LLM
# ==============================================================================
OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Model gán riêng cho từng Agent (có thể chỉnh độc lập tùy theo dung lượng VRAM/RAM)
PLANNER_MODEL: str = os.environ.get("PLANNER_MODEL", "qwen2.5-coder:7b")
CODER_MODEL: str = os.environ.get("CODER_MODEL", "qwen2.5-coder:7b")
TESTER_MODEL: str = os.environ.get("TESTER_MODEL", "qwen2.5-coder:7b")
REVIEWER_MODEL: str = os.environ.get("REVIEWER_MODEL", "qwen2.5-coder:7b")
EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

# Tham số sinh text của LLM
LLM_TEMPERATURE: float = 0.1
LLM_NUM_CTX: int = 16384
LLM_NUM_PREDICT: int = 4096
LLM_TIMEOUT: int = 300  # Giây

# ==============================================================================
# 2. CẤU HÌNH BỘ ĐIỀU PHỐI VÀ VÒNG LẶP TỰ SỬA LỖI (SELF-CORRECTION)
# ==============================================================================
# Số vòng lặp tối đa sửa lỗi giữa Planner - Coder - Tester - Reviewer
MAX_SELF_CORRECTION_CYCLES: int = 10

# Số vòng kiểm thử thành công liên tiếp cần đạt để coi là hoàn toàn ổn định
STABILITY_THRESHOLD: int = 1

# Danh sách các Agent được kích hoạt trong pipeline
# Các vai trò hỗ trợ: "planner", "coder", "tester", "reviewer"
ENABLED_AGENTS: List[str] = ["planner", "coder", "tester", "reviewer"]

# Bật/Tắt tính năng chia sẻ bộ nhớ/ngữ cảnh chung giữa các Agent (Shared Memory)
# True: Các Agent chia sẻ Blackboard, xem mã nguồn của nhau, kế thừa feedback lịch sử
# False: Chế độ cô lập (Isolated), các Agent chạy độc lập (Black-box), không share context chéo
ENABLE_SHARED_MEMORY: bool = True

# Ngôn ngữ lập trình mặc định (nếu thư mục input rỗng hoặc không nhận diện được)
# Các giá trị hợp lệ: "java", "python", "c" (hoặc None để tự suy luận từ task prompt)
DEFAULT_TARGET_LANGUAGE: str = "c"

# ==============================================================================
# 3. CẤU HÌNH SANDBOX ENGINE
# ==============================================================================
# use_docker: True để chạy cách ly an toàn trong container (cần Docker Desktop)
#             False để chạy Local Native Subprocess (siêu nhẹ trên Windows/Linux)
SANDBOX_USE_DOCKER: bool = False
SANDBOX_DOCKER_BASE_IMAGE: str = "gcc:latest"
SANDBOX_DOCKER_JAVA_IMAGE: str = "eclipse-temurin:17-jdk"
SANDBOX_TIMEOUT_SECONDS: float = 15.0
SANDBOX_MEMORY_LIMIT_MB: int = 512

# Các lệnh biên dịch / thực thi mặc định cho từng ngôn ngữ (chế độ local)
COMPILERS: Dict[str, str] = {
    "python": "python",
    "c": "gcc",
    "java_compiler": "javac",
    "java_runner": "java"
}

# ==============================================================================
# 4. CẤU HÌNH GRAPHRAG (ĐỒ THỊ TRI THỨC & EMBEDDING)
# ==============================================================================
CHROMA_DB_DIR: str = os.path.join(os.path.dirname(__file__), ".chroma_cache")
GRAPH_FILE_PATH: str = os.path.join(os.path.dirname(__file__), ".graph_cache.gml")
COLLECTION_NAME: str = "multi_file_codebase_graph"
GRAPHRAG_TOP_K: int = 3

# ==============================================================================
# 5. ĐƯỜNG DẪN THƯ MỤC LÀM VIỆC VÀ XUẤT KẾT QUẢ
# ==============================================================================
DEFAULT_OUTPUT_DIR: str = os.path.join(os.getcwd(), "generated_workspace")
DEFAULT_TEMP_SANDBOX_DIR: str = os.path.join(os.path.dirname(__file__), ".sandbox_workspace")
