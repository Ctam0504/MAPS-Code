"""Run the isolated reviewer against one of the checked-in language examples."""

import argparse
import json
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from multi_agent_system.schemas import MultiFilePlan
from reviewer_agent import ReviewerAgent


LAB_DIR = Path(__file__).resolve().parent
SEARCH_READ_DIR = LAB_DIR.parent
SOURCE_EXTENSIONS = {".c", ".h", ".java", ".py"}


def load_case(language: str):
    case_dir = LAB_DIR / "cases" / language
    workspace_dir = SEARCH_READ_DIR / language
    plan = MultiFilePlan.model_validate_json((case_dir / "plan.json").read_text(encoding="utf-8"))
    task_goal = (case_dir / "task_goal.txt").read_text(encoding="utf-8")
    testcase_path = next(case_dir.glob("testcase.*"))
    test_cases = testcase_path.read_text(encoding="utf-8")
    error_msg = (case_dir / "error.log").read_text(encoding="utf-8")
    files_dict = {
        path.relative_to(workspace_dir).as_posix(): path.read_text(encoding="utf-8")
        for path in workspace_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
    }
    return plan, task_goal, test_cases, error_msg, files_dict, workspace_dir


def main():
    parser = argparse.ArgumentParser(description="Run ReviewerAgent without the multi-agent workflow.")
    parser.add_argument("language", choices=("java", "C", "python"))
    parser.add_argument("--model", help="Override REVIEWER_MODEL for this run.")
    parser.add_argument("--base-url", help="Override OLLAMA_BASE_URL for this run.")
    args = parser.parse_args()

    plan, goal, testcase, error_msg, files_dict, workspace_dir = load_case(args.language)
    reviewer = ReviewerAgent(model_name=args.model, base_url=args.base_url)
    decision = reviewer.review(
        task_goal=goal,
        plan=plan,
        files_dict=files_dict,
        test_cases=testcase,
        error_msg=error_msg,
        workspace_dir=str(workspace_dir)
    )
    print(decision.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
