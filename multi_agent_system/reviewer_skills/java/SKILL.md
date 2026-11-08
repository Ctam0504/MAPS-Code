# Java Reviewer Skill

## Phase 1: Investigation guidance

1. Make a short worklist from the compiler log: unique `(file, symbol, line)` diagnostics. Do not add files because they are related by design or appear in an implementation chain.
2. Read only the unique project files named in that worklist and inspect only the reported lines plus their package/import declarations.
3. For an unresolved symbol, inspect its declaration once for that diagnostic group. If the plan/file list gives its path, read that path directly; use `search_code` only when the declaration path is not available there. Read the declaration's actual `package`; do not infer it from its path.
4. Do not inspect callers, implementers, sibling commands, or other dependents unless one of their own lines appears in the compiler diagnostics or the current diagnostic cannot be explained without that specific file. Do not inspect the test harness unless the log reports a harness error or test failure.
5. Stop after the worklist is covered and any unresolved discrepancy is stated. Return only the diagnostic locations and the source facts needed to explain them. For checked-exception diagnostics, inspect the relevant `throws` signatures and catch site.

## Phase 2: Verdict rules

### JAVA-ROLE-001: Responsibility attribution

Choose the responsible role from the Java diagnostic's artifact and the plan/source comparison:
- A project `.java` source that fails a contract already specified by the plan belongs to **CODER**.
- A supplied harness diagnostic or failing assertion caused by invalid test syntax, import, API use, or unsupported expectation belongs to **TESTER**.
- **PLANNER** applies only when the plan itself demonstrably omits or contradicts a required type, package/dependency relationship, or behavior. Identify that exact mismatch; `cannot find symbol` alone does not establish a plan defect.
- Preserve the compiler-reported artifact and line. Do not assign TESTER without evidence in the harness/test result, or PLANNER without evidence in the plan.

### JAVA-LOG-001: Compiler evidence is authoritative

Build the verdict from the current sandbox log and the collected source evidence together. If the result is `FAILED` and the log contains compiler errors, reject the run and address those errors; never return “no evidence of failure,” “no changes required,” or a success-shaped verdict. Investigator text, search summaries, and code overview cannot override the compiler output.

For each distinct compiler error, carry its reported file, line, symbol, and message into the audit, then explain it using the inspected source/declaration. Do not invent a different error or discard a diagnostic because another part of the code appears valid. If the inspected code seems to contradict the compiler, identify that unresolved discrepancy and check the relevant package/import or build input before concluding; do not claim the compile passed.

When the source evidence confirms that a project file uses a type from another declared package without importing it, assign **CODER**, list that use-site file in `failed_files`, and give the import using the declaration's actual package. Do not list the valid type declaration as a repair target.

### JAVA-DIAG-001: Symbols, packages, and responsibility

For each `cannot find symbol`, inspect the complete reported source and the declaration source. Read the actual `package` declaration and imports in both files; never derive a Java package name from a directory or file path. If an import is needed, use the package declared by the type's source. A type's existence elsewhere does not mean the failing source can access it.

Keep `failed_files` to project files whose code must change to address the diagnosed use. Do not list a valid declaration file merely because it defines the unresolved symbol; list it only if its declaration/package is itself wrong or incomplete.

Choose the owner only after comparing the diagnosed Java source and its declared-package/import requirements with the actual plan:
- Assign **CODER** when the plan specifies the required type/contract but production source has the wrong or missing import, package reference, declaration, or implementation.
- Assign **PLANNER** only when a specific required type, package/dependency relationship, or contract is absent or contradictory in the plan. Name that plan entry and the corresponding task requirement.
- Assign **TESTER** only for a defect evidenced in the supplied harness or a failing test result. Preserve the harness diagnostic location; do not transfer it to production code based on a matching symbol.

For harness errors, inspect the supplied test's imports and usage against the production API. Missing test imports, invalid API use, and unsupported expectations belong to TESTER when confirmed. The harness may be absent from the workspace; that alone is not a failure. Never add it to project `failed_files` or request creating it as production source.

For `package ... does not exist` or external symbols, check source roots, build command, classpath/module path, and declared dependencies. Do not invent dependencies or restructure packages without evidence.

### JAVA-DIAG-002: Types and source structure

For type, overload, constructor, generic, or static-context errors, compare the exact use with the declared API; avoid speculative casts or new APIs. For access errors, check package and modifiers; prefer a contract-consistent accessor over making fields public. For public type/file-name, duplicate-type, and class-file errors, verify package, declaration, filename, and build layout before suggesting moves or renames.

### JAVA-EXC-001: Exceptions

For `exception ... is never thrown in body of corresponding try statement`, inspect the exact `try` expressions and their compile-time method signatures, including interface and wrapper methods. Remove a catch only if none of those calls declares a compatible checked exception; otherwise repair the incorrect `throws`/handling contract. Preserve intended behavior and do not rely on a deeper implementation's `throws` clause alone.

For unresolved exception types, verify the declaration and imports. For empty catches, log-and-continue, or success-shaped fallbacks, check the failure contract before calling them defects; logging alone is not recovery. Propagate `InterruptedException` or restore the interrupt flag.

### JAVA-TEST-001: Test outcomes

Compare each assertion or expected exception with the specification and actual behavior; a test alone does not define the contract. Assign TESTER for unsupported expectations or invalid harness usage, CODER when valid tests expose a production contract violation, and PLANNER only when the plan is the demonstrated source. Report only observed failures; treat later compiler errors as cascades only when evidence supports that link.
