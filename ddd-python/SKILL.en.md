# DomainCraft: Python domain design and validation

[简体中文](SKILL.md) · English

Design objects from business rules, implement them, and check the result with executable tests. Use the user's language and follow the project's naming, architecture, and tooling conventions. For English-language tasks, use the English references linked below.

## Start with the domain

DDD defines domain language, contexts, aggregates, and invariants. This skill uses OOP to organize the implementation: decide who maintains a rule before choosing interfaces, composition, or polymorphism. Aggregate boundaries follow business consistency and lifecycles, not database foreign keys alone.

Use SOLID to review those decisions. SRP concerns reasons to change; OCP addresses known variation; LSP concerns behavioral contracts; ISP follows caller needs; DIP follows the chosen architecture's dependency direction. Class size and interface counts provide clues, not a verdict.

Choose patterns after identifying a concrete problem. Record the variation or collaboration need, simpler alternatives, and costs. After extracting a strategy, factory, or service, keep invariant ownership explicit and preserve the contract at every valid entry point.

Keep simple business operations simple. Microservices, event sourcing, asynchronous events, and transaction boundaries need support from consistency requirements and architecture decisions.

## Work through the task

First identify whether the user needs design, implementation, checking, or refactoring, then do the relevant work. For multiple packages, src layouts, native test frameworks, or databases, start with [project integration](references/large-projects.en.md). Fix the package mappings, data and runtime dependencies, change scope, and acceptance conditions before a local refactoring.

1. **Establish the rules.** Record sources, confirmation status, domain language, contexts, and invariants. Mark unconfirmed rules as assumptions.
2. **Assign responsibilities.** Explain how aggregates, value objects, application orchestration, and external ports collaborate. Define preconditions, results, exceptions, and consistency boundaries. See [object design](references/design.en.md).
3. **Choose an implementation.** Link responsibilities to business rules or architecture decisions. Explain pattern choices, alternatives, SOLID implications, and how they will be tested.
4. **Write code and comments.** Prefer clear composition. Strategies can be functions; use Protocol at meaningful substitution boundaries. Comments explain business reasons and contracts. See the [order example](assets/order_example/model.json).
5. **Build the tests.** Derive assertions from confirmed rules, covering normal inputs, boundaries, rejection, and unchanged state after rejection. Share contract tests across implementations. Add integration tests for persistence, concurrency, and idempotency requirements.
6. **Run and recheck.** Follow the [validation guide](references/validation.en.md), diagnose failures, and change the relevant code. Preserve assertions and acceptance conditions, and report skips. If two attempts at the same kind of fix make no progress, retain the failure evidence and explain the blocker.

Domain boundaries, responsibility assignments, pattern costs, and business assumptions need semantic review. Report automated results alongside unresolved design questions. To evaluate the skill's effect, use the [evaluation guide](references/benchmarking.en.md), keeping tool self-tests, reference calibration, and controlled experiments distinct.

## Run validation

The scripts use the Python 3.9+ standard library. They do not access the network, call an LLM API, or install dependencies. Replace `SKILL_DIR` below with the absolute directory containing this file.

```bash
python3 SKILL_DIR/scripts/check.py --all
python3 SKILL_DIR/scripts/check.py --project /absolute/project --all \
  --json /absolute/output/report.json --markdown /absolute/output/report.md
python3 SKILL_DIR/scripts/check.py --self-test
```

`check.py` checks the order example by default. For your own project, supply `model.json`, `architecture.json`, and discoverable unittest tests as described in the [format guide](references/model-format.en.md). `project.py` runs native project tests without requiring a model inventory for the whole codebase.

Refactoring acceptance checks both preserved behavior and concrete goals, then reports PASS/FAIL. Environment faults, timeouts, skips, and missing evidence cannot pass; the report keeps their reasons separate and produces no design score. Passing old tests still leaves the new refactoring goals to verify.

Project tests execute project code, so use a trusted environment. Prefer local fixtures for network services and document the resources needed by integration tests.

## Deliverables

Deliver the implementation, necessary comments, and tests, together with links between rules, responsibilities, decisions, and tests. JSON/Markdown reports retain passed, failed, skipped, not-run, and needs-review details, with rule IDs, locations, evidence, and suggestions.

Attach review comments to specific code and explain the business impact. Provide the documentation needed for this task so the user can understand and reproduce the result.
