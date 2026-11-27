from typing import Dict, Optional, Any, List
from multi_agent_system.schemas.multi_file_plan import MultiFilePlan
from multi_agent_system.schemas.file_spec import FileSpec


class SharedMemory:
    def __init__(self, enabled: bool = True):
        self.enabled: bool = enabled
        self.task_goal: str = ""
        self.current_plan: Optional[MultiFilePlan] = None
        self.files: Dict[str, str] = {}
        self.test_cases: str = ""
        self.agent_logs: List[Dict[str, Any]] = []

    def set_task_goal(self, task_goal: str):
        self.task_goal = task_goal

    def update_plan(self, plan: MultiFilePlan):
        if self.enabled:
            self.current_plan = plan

    def update_files(self, files: Dict[str, str]):
        if self.enabled:
            self.files = dict(files)

    def update_file(self, filepath: str, content: str):
        if self.enabled:
            self.files[filepath] = content

    def update_tests(self, test_cases: str):
        if self.enabled:
            self.test_cases = test_cases

    def get_coder_context(self, file_spec: FileSpec, all_files: Dict[str, str]) -> Dict[str, str]:
        if not self.enabled:
            isolated_context = {}
            if file_spec.filepath in all_files:
                isolated_context[file_spec.filepath] = all_files[file_spec.filepath]
            return isolated_context
        return dict(all_files)

    def get_tester_files(self, all_files: Dict[str, str]) -> Dict[str, str]:
        if not self.enabled:
            return {fp: f'// File: {fp} (Hidden in isolated mode)' for fp in all_files.keys()}
        return dict(all_files)


    def clear(self):
        self.task_goal = ""
        self.current_plan = None
        self.files.clear()
        self.test_cases = ""
        self.agent_logs.clear()
