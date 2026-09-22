# From business rules to object design

[简体中文](design.md) · English

Write down the business facts and invariants first. Then define contexts, aggregates, responsibilities, and behavioral contracts. When a concrete variation or collaboration problem appears, compare implementations and use tests to check the choice.

To place a behavior, consider which object has the needed information, the state's lifecycle, its authoritative source, and its business meaning. Every important decision should explain the rule it maintains, why it belongs there, the alternatives, and how to test it.

## When a pattern helps

| Problem already present | Possible implementation | Contract to check |
|---|---|---|
| One short business rule | An ordinary method or function | Inputs, results, and exceptions |
| Several interchangeable algorithms | Function strategies or Strategy objects | Consistent input, result, and error semantics |
| Reusable, composable conditions | Function composition or Specification | AND/OR/NOT semantics and side effects |
| Complex creation with valid initial state required | Named constructors or Factory | Every public creation path respects initial constraints |
| An external protocol differs from domain language | A port and Adapter | Translation, errors, and retry semantics |
| Growing, complex state-dependent behavior | An explicit state table or State | Every entry point rejects invalid transitions |

Python functions, closures, and Protocol often reduce boilerplate. Value objects need immutable members too: `dataclass(frozen=True)` prevents field assignment but does not freeze a list stored in a field. Business constraints still need runtime validation.

## Review with SOLID

- **SRP:** Who requests this change? Are business calculations, database mapping, and network protocols mixed together? Keep invariants that must be maintained together in one place.
- **OCP:** Which known variation does an extension point serve? Find the evidence before adding an abstraction.
- **LSP:** Does substitution preserve valid inputs, promised results, and invariants? Run the same black-box contract tests against each implementation, including failures.
- **ISP:** Give callers the operations they actually need.
- **DIP:** Check dependency direction against the chosen architecture. Define business ports around their use, and record composition-root exceptions as decisions.

## Comments and review

Module documentation explains context and responsibility. Public objects and important methods describe business meaning, preconditions, results, side effects, and exceptions. Use `Rules: ORD-001, ORD-002` to link comments to rules; behavior tests check whether those rules hold.

Explain non-obvious parameters under `Args:`. The local checker verifies parameter names; review establishes whether the explanation is accurate. Document private methods where it helps.

Review comments should identify a location, problem, and business impact, cite the rule or decision, and suggest a change and a way to verify it. Mark conclusions beyond static checking as needing review.

## What the order example covers

The bundled example includes order encapsulation, a Money value object, domain exceptions, application orchestration, a Repository Protocol, and in-memory and SQLite implementations sharing one repository contract. An ordinary method handles the current confirmation rules.

Inventory concurrency, distributed payments, an outbox, and compensation flows need their own design and integration tests. When those requirements arise, extend the existing contracts with the relevant consistency checks.
