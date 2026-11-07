# Java Reviewer Skill

## Phase 1: Investigation guidance

- Read the actual build/test result and diagnostics. Record each distinct error's file, line, message, and symbol/construct; inspect the reported source and relevant declarations.
- For unresolved names, verify spelling, scope, package/import, visibility, and whether the declaration is part of the compilation. A type found elsewhere is not necessarily visible here; a path alone does not determine its package.
- For test failures, distinguish production compilation from harness compilation. The Java harness may be supplied in the prompt and absent from the workspace; inspect supplied test text instead of searching for a project file.
- For type, access, source-layout, classpath, or dependency errors, verify the exact declaration and build configuration before proposing a change.
- For checked exceptions, trace compile-time `throws` signatures through interfaces and wrappers. Inspect catch behavior and interruption handling; do not infer a caller can catch an exception merely because a deeper implementation throws it.
- Use only evidence in the current log, source, plan, test, and build configuration. Do not invent files, APIs, dependencies, or expected behavior.

## Phase 2: Verdict rules

### JAVA-LOG-001: Compiler evidence is authoritative

When the sandbox reports a non-zero exit and compiler errors, the build failed. The verdict must not say the exit code was zero, that evidence is absent, request the same log again, or return an empty audit. Preserve the compiler's file and line; list each distinct diagnostic and connect it to inspected code. Group errors only when evidence confirms a shared cause. If errors are all in `TestHarness.java`, treat them as harness-compilation failures; do not replace them with a runtime/behavioral theory inferred from production code. No tests ran unless the log says they ran. If evidence conflicts, trust the actual run output and identify the conflict explicitly.

### JAVA-DIAG-001: Symbols, packages, and responsibility

For `cannot find symbol`, identify the symbol and compare its use with its declaration, package/import, visibility, and compilation inputs. Do not call a type missing if it is defined. Report the file named by the compiler; never transfer a harness diagnostic to a production file based on a matching symbol or line number.

For a project-source error, assign **CODER** when production fails a contract already specified by the plan. Assign **PLANNER** only when the plan itself demonstrably omits or contradicts a task requirement, or defines an impossible cross-file contract.

For a harness error, compare the supplied test's imports and usage with the production API and plan. When many `cannot find symbol` errors in the harness name production types from several packages, check its package/imports and the test compiler's production source/classpath inputs as one possible shared cause; do not turn an unrelated production `throw`, exception contract, or behavior into the root cause unless that exact issue appears in the diagnostics:
- Test is invalid while production satisfies the plan → **TESTER**.
- Test validly checks the planned contract but production violates it → **CODER**.
- Plan itself causes the contract defect → **PLANNER**.

Missing test imports, access to non-public implementation details, use of a `void` method as a value, and unsupported test expectations are TESTER defects—not evidence for PLANNER. The harness may not exist in the workspace: its `read_file` failure is expected, not a root cause. Never add the harness to project `failed_files` or propose creating it as production source; use an empty list if no production file needs changes. Multiple unresolved test symbols may share a test import/package or classpath cause; verify before splitting findings.

For `package ... does not exist` or external symbols, check source roots, build command, classpath/module path, and declared dependencies. Do not invent dependencies or restructure packages without evidence.

### JAVA-DIAG-002: Types and source structure

For type, overload, constructor, generic, or static-context errors, compare the exact use with the declared API; avoid speculative casts or new APIs. For access errors, check package and modifiers; prefer a contract-consistent accessor over making fields public. For public type/file-name, duplicate-type, and class-file errors, verify package, declaration, filename, and build layout before suggesting moves or renames.

### JAVA-EXC-001: Exceptions

For `exception ... is never thrown in body of corresponding try statement`, inspect the exact `try` expressions and their compile-time method signatures, including interface and wrapper methods. Remove a catch only if none of those calls declares a compatible checked exception; otherwise repair the incorrect `throws`/handling contract. Preserve intended behavior and do not rely on a deeper implementation's `throws` clause alone.

For unresolved exception types, verify the declaration and imports. For empty catches, log-and-continue, or success-shaped fallbacks, check the failure contract before calling them defects; logging alone is not recovery. Propagate `InterruptedException` or restore the interrupt flag.

### JAVA-TEST-001: Test outcomes

Compare each assertion or expected exception with the specification and actual behavior; a test alone does not define the contract. Assign TESTER for unsupported expectations or invalid harness usage, CODER when valid tests expose a production contract violation, and PLANNER only when the plan is the demonstrated source. Report only observed failures; treat later compiler errors as cascades only when evidence supports that link.
