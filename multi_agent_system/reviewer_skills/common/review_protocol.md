# Shared Reviewer Protocol

- Treat sandbox output as evidence, not as the complete explanation of root cause.
- Review the first failure that stopped execution before considering later or hypothetical issues. Do not replace it with an unrelated test, API, symbol, or defect that is absent from the current log and evidence.
- Separate where a failure is reported from the code or build contract that caused it.
- Check the relevant source and caller/callee contract before assigning responsibility.
- Treat later diagnostics as possible cascades from an earlier failure.
- Every proposed code change must be derivable from the reported source, plan, or specification. Do not invent methods, files, imports, or implementation examples.
- Do not infer a defect from a pattern alone when it may be intentional; verify the specification and observable behavior.
- Assign the issue to the role responsible for the verified failing file: project source to Coder, test harness to Tester, and a demonstrated plan/interface defect to Planner. If evidence is incomplete, state the limitation while still selecting the best-supported responsible role.
- Recommend the smallest change that addresses the verified cause. Phase 1 gathers facts only; phase 2 decides.
