# Python Reviewer Skill

## Phase 1: Investigation guidance

- For `SyntaxError`, `IndentationError`, or `py_compile` failures, inspect the first reported file and line, then check nearby delimiters, indentation, and the preceding statement. Later syntax errors may be cascades.
- For an import-related `SyntaxError`, inspect the exact source line and Python grammar. Distinguish invalid import syntax from a valid import that later fails module resolution; derive any correction from the package layout and project import convention.
- For `ModuleNotFoundError` or `ImportError`, compare the exact import with the plan's file paths and the source definition of the imported symbol. Derive a module path from the actual planned file path; never invent a module or package path.
- Check the project's stated import convention and actual package structure. Use an absolute import when that is the project contract; do not suggest `from . import Symbol` unless the package's `__init__.py` explicitly exports that symbol.
- Attribute a wrong import in generated source to Coder when the plan contains the correct module/file and its interface. Attribute it to Planner only when the plan itself omits or contradicts a required module, dependency, or interface.
- For a traceback, inspect the original exception and every distinct project/test-harness frame relevant to it. Read the failing expression and the affected file's imports before deciding the cause.
- For `NameError`, search for the referenced name's definition, then verify that the failing module imports it. If the definition exists and the specification requires its use, a missing import in a project module is a local implementation defect; a missing import in the test harness is a test defect.
- For chained exceptions (`During handling of the above exception`), distinguish the original exception from a secondary failure while evaluating or running an `except` handler. Inspect the handler's exception type and imports; report both defects when independently supported.
- When a test runner reports multiple failing tests, treat each test outcome as separate unless a traceback explicitly shows exception chaining or shared causation. For each outcome, identify its own final diagnostic and relevant source frame; do not merge unrelated failures into one cause.
- Attribute a runtime exception to the file and expression where the traceback shows it was raised. A test frame that calls project code does not make the test the source of a project exception, and a symbol mentioned by a test's `except` clause is not evidence that the test omitted its import.
- For a failing test, compare the assertion's expected value with the task specification and the implementation's actual behavior.
- For an expected-exception test, compare the exception actually raised with the exception type and message the test handles or asserts, then check whether that expectation is supported by the specification or plan. Verify the harness imports directly before claiming an import is missing. Do not invent an expected behavior to make the test or implementation appear correct.
- If reviewing exception handling, inspect the `except` block and its callers to determine whether failure is propagated, represented, or hidden.

## Phase 2: Verdict rules

### PY-ROLE-001: Responsibility attribution

Choose the responsible role from the Python failure location and the specification/plan comparison:
- A defect in a project module's implementation or imports belongs to **CODER** when the plan specifies the required behavior or interface.
- A defect in the supplied test harness belongs to **TESTER** when its syntax, imports, API use, or expected result is wrong for the specified contract.
- **PLANNER** applies only when the plan itself omits or contradicts a required module, dependency, interface, or behavior. Identify that exact mismatch; a project traceback or test failure alone is not evidence against the plan.
- Base attribution on the traceback frame, failing expression, import resolution, or assertion result. A test frame calling project code does not by itself make the test responsible.

### PY-DIAG-001: Syntax and indentation diagnostics

Treat the interpreter's file, line, and error text as the location to investigate, not proof that the exact token on that line is the root cause. Check the preceding statement and nearby block structure. Attribute the issue only after confirming the source and expected syntax.

When the sandbox stops with a `SyntaxError`, diagnose that syntax failure before discussing hypothetical runtime or test failures. Quote the actual source line and recommend a correction derived from Python syntax, surrounding code, and the project layout. Do not replace this diagnosis with an unrelated defect inferred from test intent.

### PY-DIAG-002: Import and module resolution

For `ModuleNotFoundError` and `ImportError`, distinguish project-module path/package problems from unavailable third-party dependencies and errors raised while importing a module. Verify the import name, package layout, environment, and run command. Do not prescribe installing a package without evidence it is an intended dependency.

If a generated import targets a module path absent from the plan while the symbol is defined in a different planned file, identify the exact mismatched import and derive the replacement from that file's path and declared package. Do not tell the Planner to restructure a plan whose file contract already places the definition correctly.

### PY-DIAG-003: Runtime traceback

Use the exception chain and traceback frames to locate the failing operation. Check whether the caller supplied a value that violates the function's contract or the implementation mishandled a valid input. Do not treat the topmost framework/test frame as the root cause by default. When an exception occurs while handling another exception, retain the first exception as the primary failure and investigate the handler failure separately. In test-runner output containing multiple tracebacks, distinguish separate test outcomes from a chained exception and analyze each outcome using its own evidence.

### PY-DIAG-004: Undefined name

For `NameError`, identify the exact name and the module/frame where it is evaluated. Search the project for its definition and inspect the failing module's imports and the plan/specification. If the name is defined and required but not imported in a project source file, classify the defect as CODER/LOCAL. If a test harness refers to a defined project exception but omits its own import, classify that defect as TESTER/TESTCASE only when the traceback locates the undefined name in the harness and the import is actually absent. Do not confuse an undefined name in an `except` clause with the original exception that caused control to enter that clause. The exception name and file/line in the current traceback are authoritative: do not replace them with a different exception from the task description, test intent, or another run.

When one traceback contains both a project defect and a test-harness defect, identify the original failure as primary and list the independently confirmed secondary issue in the audit. Choose the primary target supported by the original failure. Do not apply this exception-chain rule to separate test outcomes; analyze those independently.

### PY-EXC-001: Exception swallowed or obscured

Inspect `except` blocks that are empty, use only `pass`, log and continue, or return a default value. Confirm that the exception can occur on the relevant path and that the caller cannot distinguish failure from a valid result. A fallback is not a defect if it is specified, safe, and observably represented where required. Recommend handling the specific exception, propagating it, or returning an explicit failure result; do not require propagation when the contract intentionally recovers.

### PY-TEST-001: Assertion failure

Compare expected and actual values with the task specification and public contract. Trace the actual value to the code that produced it and quote the assertion or expected-exception clause that failed. Assign the issue to the implementation only when behavior violates that contract; assign it to the test only when the test expectation is contradicted by the specification. If the contract does not define the disputed behavior, report that limitation instead of inventing a required state transition, exception, or message.
