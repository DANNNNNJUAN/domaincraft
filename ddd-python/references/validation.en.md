# Running local checks

[简体中文](validation.md) · English

`check.py` checks model references, architecture, comments, and business tests. Use the [project acceptance entry point](large-projects.en.md) for multiple packages or native project tests. Both retain execution evidence.

These commands need only the Python 3.9+ standard library: no pytest, network access, or API key. Absolute paths let you run them from any directory. For package mappings and configuration stored outside the project root, see the [layout configuration](model-format.en.md).

```bash
python3 /absolute/ddd-python/scripts/check.py --all
python3 /absolute/ddd-python/scripts/check.py --project /absolute/project --model --comments
python3 /absolute/ddd-python/scripts/check.py --project /absolute/project --architecture
python3 /absolute/ddd-python/scripts/check.py --project /absolute/project --tests --timeout 60
python3 /absolute/ddd-python/scripts/check.py --self-test
```

`--all` includes package completeness, model references, architecture, comments, and business tests. It is also the default when no checks are selected. `--self-test` runs tool regressions separately. Save reports with `--json PATH --markdown PATH`.

## Read the result

| Exit code | Meaning |
|---|---|
| 0 | Selected automated checks passed |
| 1 | A rule failed, or failed/skipped tests left insufficient evidence |
| 2 | Input, configuration, syntax, or runner error |

`semantic_status` records semantic review separately. A pending review alone does not cause a nonzero exit code. Unselected checks show `not_run`. Reports also list individual passed, failed, skipped, and needs-review items.

Tests use the current Python interpreter in a separate process, with a default 60-second timeout and captured Python standard output and error. No tests, discovery failures, runner faults, timeouts, and skips cannot count as passing evidence. The subprocess executes project code, so use a trusted test environment.

## Coverage

| Check | Automated evidence | Further judgment needed |
|---|---|---|
| Model references | IDs, links, rule ownership, implementation symbols, and test references | Whether business assumptions hold |
| Static architecture | Imports, forbidden modules, layer dependencies, and module cycles in the configured scope | Other reflective behavior and whether the declared scope is complete |
| Comment structure | Documentation presence, Rules references, and Args parameter names | Whether comments accurately explain the business |
| Business execution | Assertions, exceptions, state after rejection, repository contracts, and SQLite integration | Whether tests cover the important business cases |

The report's `source_roots` describes static coverage. Design review addresses domain boundaries, the application of SOLID, and pattern choices.

## Write regressions

Start with black-box assertions from confirmed requirements, then use valid cases and injected defects to check the tools. Bundled tests cover invariants, state transitions, invalid-input rejection, value objects, and contracts across adapters.

Tool tests use temporary directories to inject dangling references, illegal imports, cycles, stale comments, and broken business behavior. They check actual behavior and exit status. Evaluate the skill's natural-language design decisions separately through realistic tasks.
