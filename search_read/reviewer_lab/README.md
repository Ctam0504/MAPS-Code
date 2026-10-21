# Reviewer lab

Run the copied reviewer directly against the Java, C, or Python workspace. This does not start the planner, coder, tester, sandbox, or coordinator workflow.

From the repository root:

```powershell
python .\search_read\reviewer_lab\run_review.py python
python .\search_read\reviewer_lab\run_review.py java
python .\search_read\reviewer_lab\run_review.py C
```

The runner loads the source workspace from `search_read/<language>/` and the matching task, plan, testcase, and sandbox error log from `search_read/reviewer_lab/cases/<language>/`. It invokes the configured reviewer model directly; `--model` and `--base-url` can override the defaults for a run.

`reviewer_agent.py` is the isolated, editable reviewer copy. Its audit prompt, JSON decision parsing, and `search_grep`-then-`read_file` tool loop live together in that file. The checked-in testcases intentionally contain incorrect expectations; their logs are examples for testing whether the reviewer attributes failures to TESTER rather than changing correct source code.
