"""
multi_agent_system.tools.workspace_tools
========================================
Tập hợp công cụ thao tác và tra cứu workspace cho Agent (Reviewer)
dựa trên FileManagementToolkit chuẩn của LangChain (langchain_community)
và bổ sung công cụ tìm kiếm nội dung mã nguồn (search_code).
"""

import os
from pathlib import Path
from typing import List, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_community.agent_toolkits import FileManagementToolkit


class SearchCodeInput(BaseModel):
    query: str = Field(..., description="Symbol, tên hàm, tên class, hoặc biến DUY NHẤT. Input chỉ nhận 1 từ khóa duy nhất ")


class SearchCodeTool(BaseTool):
    name: str = "search_code"
    description: str = (
        "Tìm kiếm từ khóa, symbol, tên hàm, class hoặc đoạn mã trong tất cả các tệp mã nguồn "
        "thuộc workspace. Trả về danh sách đường dẫn tệp kèm số dòng chứa từ khóa."
    )
    args_schema: Type[BaseModel] = SearchCodeInput
    workspace_dir: Path

    def __init__(self, workspace_dir: Path, **kwargs):
        super().__init__(workspace_dir=workspace_dir, **kwargs)

    def _run(self, query: str) -> str:
        if not query or not query.strip():
            return "Lỗi: query tìm kiếm không được để trống."

        query_str = query.strip()
        matched_results = {}
        ignored_dirs = {".git", "__pycache__", "node_modules", "target", "build", "dist", ".idea", ".vscode"}

        try:
            for root, dirs, files in os.walk(self.workspace_dir):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
                for file in files:
                    if file.endswith((".class", ".o", ".obj", ".exe", ".bin", ".pyc")):
                        continue

                    full_path = Path(root) / file
                    try:
                        rel_path = full_path.relative_to(self.workspace_dir).as_posix()
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f, 1):
                                if query_str.lower() in line.lower():
                                    if rel_path not in matched_results:
                                        matched_results[rel_path] = []
                                    matched_results[rel_path].append(f"Dòng {idx}: {line.strip()[:150]}")
                    except Exception:
                        continue

            if not matched_results:
                return f"Không tìm thấy file nào chứa mã/từ khóa: '{query_str}'"

            output_lines = [f"Tìm thấy '{query_str}' trong {len(matched_results)} tệp:"]
            for rel_path, lines in matched_results.items():
                output_lines.append(f"\n📄 Tệp: `{rel_path}`")
                for line_preview in lines[:5]:  # Giới hạn 5 preview mỗi file
                    output_lines.append(f"  - {line_preview}")
                if len(lines) > 5:
                    output_lines.append(f"  ... (và {len(lines) - 5} vị trí khác)")

            return "\n".join(output_lines)
        except Exception as e:
            return f"Lỗi khi thực thi search_code: {str(e)}"


class WorkspaceTools:
    """
    Tập hợp và quản lý các công cụ File Management cho Reviewer Agent
    sử dụng FileManagementToolkit từ LangChain và Custom SearchCodeTool.
    """

    def __init__(
        self,
        workspace_dir: str,
        selected_tools: Optional[List[str]] = None
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        if not self.workspace_dir.exists():
            raise FileNotFoundError(f"Thư mục workspace không tồn tại: {self.workspace_dir}")

        self.selected_tools = selected_tools

        # Tách selected_tools cho FileManagementToolkit (loại bỏ search_code nếu có)
        toolkit_tools = None
        if selected_tools is not None:
            toolkit_tools = [t for t in selected_tools if t != "search_code"]

        self.toolkit = FileManagementToolkit(
            root_dir=str(self.workspace_dir),
            selected_tools=toolkit_tools
        )

    def get_tools(self) -> List[BaseTool]:
        """Trả về danh sách các LangChain BaseTool bao gồm cả search_code."""
        tools = self.toolkit.get_tools()

        # Thêm SearchCodeTool nếu không chỉ định selected_tools hoặc selected_tools có chứa 'search_code'
        if self.selected_tools is None or "search_code" in self.selected_tools:
            tools.append(SearchCodeTool(workspace_dir=self.workspace_dir))

        return tools

    @classmethod
    def get_tool_definitions(cls, workspace_dir: str, selected_tools: Optional[List[str]] = None) -> List[dict]:
        instance = cls(workspace_dir=workspace_dir, selected_tools=selected_tools)
        tools = instance.get_tools()
        
        definitions = []
        for tool in tools:
            schema = {}
            if tool.args_schema:
                if hasattr(tool.args_schema, "model_json_schema"):
                    schema = tool.args_schema.model_json_schema()
                elif hasattr(tool.args_schema, "schema"):
                    schema = tool.args_schema.schema()
                    
            definitions.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": schema
                }
            })
        return definitions