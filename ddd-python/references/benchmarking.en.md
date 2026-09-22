# Evaluating the skill's effect

[简体中文](benchmarking.md) · English

Tool self-tests answer whether the checker works as specified. To ask whether the skill improves refactoring results, use independent tasks, independent acceptance checks, and comparable experimental conditions.

## Compare conditions

Fix the starting code, task, model, budget, and evaluator version. Then compare three conditions: no skill, design guidance only, and the complete skill. Start each attempt with clean context so guidance from one condition cannot carry into another. Freeze the candidate before running acceptance. Repeatedly editing an answer after seeing acceptance failures is development calibration.

Repeat runs and retain failures, timeouts, and missing submissions. Record old-behavior regressions, new rules, substitution contracts, dependency boundaries, and semantic review separately, with PASS/FAIL for each applicable check. Do not combine class, pattern, or comment counts into a design score.

## Identify the source of each result

External benchmark prepare/run/compare tools can validate saved code as part of the experiment infrastructure. Test execution needs no LLM API; generating candidates is a separate stage. Label reference implementations written with knowledge of the tests as calibration.

Use development tasks to improve the tools and unseen holdout tasks to evaluate generalization. A task or reference answer already examined is no longer a blind holdout. When model or budget records are incomplete, report observed differences between the code artifacts.

Comment accuracy, domain boundaries, and pattern costs still need semantic review. Save those judgments alongside the executable results so they can be revisited.
