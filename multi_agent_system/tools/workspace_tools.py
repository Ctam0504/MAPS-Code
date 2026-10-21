"""
multi_agent_system.tools.workspace_tools
========================================
Tập hợp công cụ thao tác và tra cứu workspace cho Agent (Reviewer)
dựa trên FileManagementToolkit chuẩn của LangChain (langchain_community).
"""

from pathlib import Path
from typing import List, Optional
from langchain_core.tools import BaseTool
from langchain_community.agent_toolkits import FileManagementToolkit


class WorkspaceTools:
    """
    Tập hợp và quản lý các công cụ File Management cho Reviewer Agent
    sử dụng FileManagementToolkit từ LangChain.
    """

    def __init__(
        self,
        workspace_dir: str,
        selected_tools: Optional[List[str]] = None
    ):
        """
        Khởi tạo FileManagementToolkit với sandboxing tại workspace_dir.

        Args:
            workspace_dir: Đường dẫn thư mục gốc (root_dir) giới hạn thao tác của Agent.
            selected_tools: Danh sách các tool cụ thể muốn sử dụng. 
                            Ví dụ: ["read_file", "list_directory", "file_search"]
                            Nếu None, Toolkit sẽ load đầy đủ các tool mặc định.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        if not self.workspace_dir.exists():
            raise FileNotFoundError(f"Thư mục workspace không tồn tại: {self.workspace_dir}")

        # Khởi tạo LangChain FileManagementToolkit với cơ chế Sandboxing
        self.toolkit = FileManagementToolkit(
            root_dir=str(self.workspace_dir),
            selected_tools=selected_tools
        )

    def get_tools(self) -> List[BaseTool]:
        """Trả về danh sách các LangChain BaseTool để truyền thẳng vào Agent."""
        return self.toolkit.get_tools()

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