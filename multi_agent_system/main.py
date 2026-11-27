"""
multi_agent_system.main
=======================
Điểm khởi chạy chính (CLI Entrypoint) của Hệ thống Multi-Agent Code Generation Đa Tệp.
"""

import multi_agent_system.config as config
import os
import io
import sys
# Đảm bảo in tiếng Việt trên console Windows không bị UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import asyncio
import argparse

# Đảm bảo đường dẫn gốc được nạp vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from multi_agent_system.coordinator import MultiAgentCoordinator
from multi_agent_system import config

DEFAULT_SYSTEM_MODE = "planner-coder-tester-reviewer-tools"
SYSTEM_MODES = {
    "coder": {
        "enabled_agents": ["coder"],
        "reviewer_tools": False,
        "reviewer_skills": False,
    },
    "planner-coder": {
        "enabled_agents": ["planner", "coder"],
        "reviewer_tools": False,
        "reviewer_skills": False,
    },
    "planner-coder-tester-reviewer": {
        "enabled_agents": ["planner", "coder", "tester", "reviewer"],
        "reviewer_tools": False,
        "reviewer_skills": False,
    },
    "planner-coder-tester-reviewer-tools": {
        "enabled_agents": ["planner", "coder", "tester", "reviewer"],
        "reviewer_tools": True,
        "reviewer_skills": True,
    },
}

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Hệ thống Multi-Agent Code Generation Đa Tệp (Python, Java, C) với GraphRAG và Reviewer Audit"
    )
    parser.add_argument(
        "--mode",
        choices=SYSTEM_MODES,
        default=DEFAULT_SYSTEM_MODE,
        help=(
            "Chế độ tác tử: coder, planner-coder, planner-coder-tester-reviewer "
            "hoặc planner-coder-tester-reviewer-tools "
            f"(mặc định: {DEFAULT_SYSTEM_MODE})"
        )
    )
    parser.add_argument(
        "--task", "-t",
        type=str,
        default="",
        help="Mô tả yêu cầu bài toán cần sinh mã nguồn"
    )
    parser.add_argument(
        "--input-dir", "-i",
        type=str,
        default="",
        help="Đường dẫn thư mục đầu vào chứa codebase sẵn có (có thể để trống)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Đường dẫn thư mục lưu mã nguồn kết quả (mặc định: nếu có input folder thì dùng cùng thư mục, nếu không thì dùng generated_workspace)"
    )
    parser.add_argument(
        "--language", "-l",
        type=str,
        choices=["python", "java", "c"],
        default=None,
        help="Chỉ định cưỡng bức ngôn ngữ lập trình: 'python', 'java', 'c' (nếu bỏ trống hệ thống tự nhận diện)"
    )
    parser.add_argument(
        "--cycles", "-c",
        type=int,
        default=config.MAX_SELF_CORRECTION_CYCLES,
        help=f"Số vòng lặp tự sửa lỗi (Self-Correction) tối đa (mặc định: {config.MAX_SELF_CORRECTION_CYCLES})"
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        default=config.SANDBOX_USE_DOCKER,
        help="Kích hoạt chế độ Sandbox bằng Docker Container thay vì Local Subprocess"
    )
    parser.add_argument(
        "--share-mem",
        action=argparse.BooleanOptionalAction,
        default=config.ENABLE_SHARED_MEMORY,
        help="Bật/Tắt tính năng chia sẻ bộ nhớ (Shared Memory) giữa các Agent (mặc định theo config)"
    )
    return parser.parse_args()


async def main_async():
    args = parse_arguments()

    task_prompt = args.task
    if not task_prompt:
        print("\n" + "=" * 60)
        print("🤖 HỆ THỐNG MULTI-AGENT CODE GENERATION ĐA TỆP (PYTHON, JAVA, C)")
        print("=" * 60)
        task_prompt = input("👉 NHẬP YÊU CẦU BÀI TOÁN (Task Goal): ").strip()
        if not task_prompt:
            print("❌ Yêu cầu không được để trống. Thoát chương trình.")
            sys.exit(1)

    input_folder = args.input_dir.strip().strip('"').strip("'")
    if not input_folder and sys.stdin.isatty():
        entered_folder = input("👉 THIẾT LẬP FOLDER INPUT (Đường dẫn folder tiền sắp xếp, Enter nếu thư mục rỗng): ").strip().strip('"').strip("'")
        if entered_folder:
            input_folder = entered_folder

    if input_folder and not os.path.exists(input_folder):
        print(f"⚠️ Cảnh báo: Thư mục input '{input_folder}' không tồn tại. Coi như thư mục rỗng.")
        input_folder = None

    # Đặt thư mục output bằng thư mục input nếu đã chỉ định (sửa trực tiếp trong cùng folder)
    output_dir = args.output_dir if args.output_dir else (input_folder if input_folder else config.DEFAULT_OUTPUT_DIR)
    mode_config = SYSTEM_MODES[args.mode]
    coordinator = MultiAgentCoordinator(
        output_dir=output_dir,
        max_cycles=args.cycles,
        use_docker=args.docker,
        enable_shared_memory=args.share_mem,
        enabled_agents=mode_config["enabled_agents"],
        enable_reviewer_tools=mode_config["reviewer_tools"],
        enable_reviewer_skills=mode_config["reviewer_skills"],
    )

    await coordinator.run(
        task_prompt=task_prompt,
        input_folder=input_folder,
        target_language=args.language
    )


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
