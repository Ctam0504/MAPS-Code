# C Reviewer Skill

## Phase 1: Investigation guidance

- Distinguish compiler diagnostics from linker diagnostics and runtime/test failures. Inspect the command that produced the output as well as the first actionable diagnostic.
- For `undeclared` or implicit-function diagnostics, inspect the use, visible declaration/prototype, included headers, and include paths.
- For `undefined reference`, inspect the symbol declaration and definition, then verify that the defining source/object is included in the link command and that symbol names/linkage match.
- Derive header and source paths from the actual planned files and build command. Do not invent a header or source path; distinguish an incorrect include/build reference from a missing or contradictory file dependency in the plan.
- For type/conflicting declaration diagnostics, compare the declarations and definitions across relevant headers and source files.
- For runtime failures, inspect the failing test/assertion and check return values, pointer ownership, bounds, and resource lifetime relevant to the failure.
- If error handling is relevant, inspect whether return codes, `errno`, allocation failures, and cleanup paths are checked consistently with the API contract.

## Phase 2: Verdict rules

### C-DIAG-001: Compile-time undeclared symbol

For undeclared identifiers or implicit function declarations, verify the identifier spelling, declaration/prototype, header inclusion, include path, and declaration order where relevant. Do not conclude the implementation is missing until checking whether the required declaration is visible.

When compilation stops on a syntax diagnostic, analyze that reported construct first. Base the minimal correction on the actual source line and C grammar; do not substitute a speculative API or unrelated test failure.

### C-DIAG-002: Link-time undefined reference

Classify `undefined reference` as a link-stage diagnostic. Check that a definition exists, its signature/name and linkage match the declaration, and the defining `.c` file or object is included in the actual link command. Do not infer a missing implementation from the message alone.

### C-DIAG-003: Conflicting types and duplicate definitions

Compare all declarations/definitions of the symbol, including parameter and return types, and inspect header inclusion/guards. Distinguish a conflicting declaration from multiple external definitions; recommend changing only the inconsistent or duplicate definition confirmed by evidence.

### C-DIAG-004: Warnings

A warning is not automatically a build failure. Check the compiler flags (including whether warnings are promoted to errors), the exact warning, and whether it indicates behavior relevant to the task. Do not claim a warning caused failure unless the command/status supports that conclusion.

### C-ERR-001: Error result ignored

Inspect calls that return status values and operations that signal failure through `NULL`/`errno`. Verify the failure path and whether callers can observe it. A deliberately ignored result is not automatically a defect if the API contract and context show it is safe. For confirmed failures, recommend handling/reporting the result and preserving required cleanup.

### C-MEM-001: Allocation and resource lifetime

When evidence points to memory/resource handling, trace ownership and lifetime across allocation, use, and release. Check allocation failure before dereference and avoid reporting a leak or double free without a path demonstrating it.

### C-TEST-001: Harness failure

Compare the harness assertion and actual behavior to the task specification. A failed assertion alone does not establish whether the implementation or test expectation is wrong.

### C-DIAG-005: Diagnostic cascade

Prioritize the first actionable compiler diagnostic. Later errors may be caused by an earlier syntax/declaration failure; verify before recommending separate changes.
