import json
from types import SimpleNamespace

import pytest

from multi_agent_system.tools.workspace_tools import WorkspaceTools
from reviewer_agent import ReviewerAgent
from run_review import load_case


def test_language_cases_load_with_matching_workspace():
    for language in ("java", "C", "python"):
        plan, goal, testcase, error, files, workspace = load_case(language)
        assert plan.target_language == ("c" if language == "C" else language)
        assert goal and testcase and error
        assert files
        assert workspace.is_dir()


def test_reviewer_runs_search_then_reads_only_discovered_path(tmp_path):
    source = tmp_path / "src" / "sample.py"
    source.parent.mkdir()
    source.write_text("class PaymentProcessor:\n    pass\n", encoding="utf-8")
    reviewer = ReviewerAgent()

    def tool_call(call_id, name, arguments):
        return SimpleNamespace(
            id=call_id,
            function=SimpleNamespace(name=name, arguments=json.dumps(arguments))
        )

    tool_messages = [
        SimpleNamespace(
            content=None,
            tool_calls=[tool_call("search-1", "search_grep", {
                "query": "PaymentProcessor",
                "path": "src"
            })]
        ),
        SimpleNamespace(
            content=None,
            tool_calls=[tool_call("read-1", "read_file", {
                "path": "src/sample.py",
                "line_range": "1-2"
            })]
        ),
        SimpleNamespace(content='{"target":"CODER"}', tool_calls=None)
    ]
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=message)])
        for message in tool_messages
    ]
    requested_messages = []

    def fake_create(**kwargs):
        requested_messages.append(list(kwargs["messages"]))
        return responses.pop(0)

    reviewer.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=fake_create)
        )
    )
    result = reviewer._call_with_workspace_tools(
        "test prompt",
        WorkspaceTools(str(tmp_path))
    )

    assert result == '{"target":"CODER"}'
    assert "src/sample.py:1:" in requested_messages[1][-1]["content"]
    assert "class PaymentProcessor" in requested_messages[2][-1]["content"]


def test_reviewer_does_not_read_before_search(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text("class PaymentProcessor:\n    pass\n", encoding="utf-8")
    reviewer = ReviewerAgent()
    read_call = SimpleNamespace(
        id="read-1",
        function=SimpleNamespace(
            name="read_file",
            arguments=json.dumps({"path": "sample.py", "line_range": "1-2"})
        )
    )
    final_message = SimpleNamespace(content='{"target":"CODER"}', tool_calls=None)
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=None,
            tool_calls=[read_call]
        ))]),
        SimpleNamespace(choices=[SimpleNamespace(message=final_message)])
    ]
    reviewer.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: responses.pop(0))
        )
    )

    with pytest.raises(RuntimeError, match="without searching"):
        reviewer._call_with_workspace_tools("test prompt", WorkspaceTools(str(tmp_path)))
