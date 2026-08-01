# adhd — installed 2026-08-01

**Source:** https://github.com/UditAkhourii/adhd (`skills/adhd/SKILL.md`), MIT, author Udit Akhouri.
Paper: *ADHD: Parallel Divergent Ideation for Coding Agents*. Site: https://adhdstack.github.io/

**What it does:** fans out N isolated parallel Agent calls under different "cognitive frames"
(hardware engineer, regulator, 10-year-old, $0 budget, …), each forbidden from evaluating, then a separate
critic pass scores, clusters, prunes traps, and deepens the survivors. Tree-of-thought with pruning.

**Reviewed before install (2026-08-01):** no network calls, no credential access, no destructive commands,
no writes outside the conversation. It is a prompting technique, not an integration. The one `npm install`
string in the file refers to the author's standalone CLI and is not an instruction the skill executes.

**Cost:** ~10 Agent calls, 5–10x a single answer. Its own pre-flight gate aborts on closed phrasing
("quick", "standard", "canonical") and on questions with one canonical answer.

**How it fits this project:** the natural use is **stat ideation for the calibration** — the current job is
generating candidate signals nobody would think of, which is exactly what a divergence phase is for. It is
explicitly *not* for coding, and it must not be used to generate stats we then report as findings: anything
it produces is a HYPOTHESIS that still has to survive the backtest in
[[testing/calibration_scope]] (fit 2023 → predict 2024 → beat the null). Ideation is free; belief is earned.

**Invocation:** `/adhd <problem>`. It is user-triggered by design — do not self-invoke.
