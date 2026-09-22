# Integrating multi-package projects and checking refactorings

[简体中文](large-projects.md) · English

Use `scripts/project.py` to connect an existing Python project to its own test environment and refactor locally through inspect, baseline, and verify. `check.py` remains the entry point for model references and comment checks. The tools use the standard library and make no LLM API calls; the project supplies its own dependencies.

## Define the scope first

Read the build configuration, package inventory, test configuration, and migration entry points. Establish how files map to Python import names. Preserve the project's domain language, public interfaces, and transaction agreements while defining this change's boundary.

Here is a version 2 configuration:

```json
{
  "version": 2,
  "packages": [
    {
      "name": "orders",
      "root": "packages/orders",
      "imports": [{"path": "packages/orders/src", "prefix": ""}],
      "public": ["orders.api"],
      "allow": ["stock"],
      "external": ["typing_extensions"],
      "forbidden": ["sqlite3", "psycopg"]
    },
    {
      "name": "stock",
      "root": "packages/stock",
      "imports": [{"path": "packages/stock/src", "prefix": ""}],
      "public": ["stock.api"],
      "allow": [],
      "external": ["sqlalchemy", "psycopg"]
    }
  ],
  "tracked_paths": ["."],
  "exclude": [".venv/**", "build/**", ".pytest_cache/**"],
  "protected_paths": ["tests/**/*.py", "pyproject.toml"],
  "allowed_changes": ["packages/orders/src/orders/service.py"],
  "architecture_policy": "strict",
  "runtime_edges": [
    {"from": "orders", "to": "stock", "kind": "event", "evidence": "OrderPlaced event subscription in bootstrap.py"}
  ],
  "data_resources": [
    {"name": "stock_table", "readers": ["orders"], "writers": ["stock"], "paths": ["migrations/**"], "evidence": "Stock table ownership and migration manifest"}
  ],
  "goals": [
    {"id": "delegation", "kind": "calls", "path": "packages/orders/src/orders/service.py", "symbol": "place_order", "callee": "stock.reserve"}
  ],
  "jobs": [
    {"id": "regression", "phase": "both", "format": "junit", "argv": [".venv/bin/python", "-m", "pytest", "tests", "--junitxml={evidence}"], "cwd": ".", "timeout": 600}
  ]
}
```

### Package mappings and dependencies

`imports.path` is relative to the project root. With an empty `prefix`, `src/acme/orders.py` resolves to `acme.orders`. If the mapping points directly to `orders/`, use `prefix: orders`. Duplicate import names are rejected. Import names may differ from distribution names; the project's dependency manager still handles distribution-version conflicts.

`public` lists module prefixes other packages may import. `allow` lists permitted package dependencies. References within the same package are not restricted by `public`. Ordinary, relative, and conditional imports enter the static graph, which checks module and package cycles. Declare external libraries in `external`; unknown and wildcard imports produce findings. The Python interpreter running the checker must support the project's syntax.

### File coverage

Static analysis covers configured sources. Include relevant data, configuration, and migration files in `tracked_paths` so their changes can be detected. Usually, track the whole project and exclude build outputs. `.git`, `__pycache__`, and `.pyc` are ignored by default.

Packages marked `language: "native"` participate in change-scope and native-test acceptance. They need no Python import mapping and receive no Java/JavaScript static architecture analysis. Materialize symbolic links in a separate working copy and record how they were handled, leaving the original project's links intact.

## Inspect the impact

```bash
python3 SKILL_DIR/scripts/project.py inspect \
  --project /absolute/project --config /absolute/acceptance.json \
  --changed packages/stock/src/stock/api.py \
  --output /absolute/evidence/inspection
```

The report lists imports, transitively affected packages, declared event/RPC/configuration relationships, and shared-data readers and writers. Runtime and data relationships come from verifiable project information. Shared resources propagate impact conservatively in both directions.

Unknown changed files, unresolved imports, and dynamic loading expand the impact to all configured packages. Dynamic imports fail by default. For a justified exception, add module and reason under `dynamic_import_exceptions` and declare the runtime relationships. The exception remains in the report and requires full-scope validation.

The impact graph explains scope. `verify` always runs all configured jobs; it does not use the graph to skip tests.

## Run the project's tests

Each job supplies an `argv` array to start a process directly. Supported placeholders are `{python}`, `{project}`, `{skill}`, `{artifacts}`, and `{evidence}`. `cwd` stays within the project. `env` can supply test settings; keep passwords and production connections in the environment rather than in the configuration file.

| Setting | Meaning |
|---|---|
| `phase: both` | Run on baseline and candidate; the candidate must retain previously passing test IDs |
| `phase: after` | Run new-requirement or refactoring-goal acceptance only on the candidate |
| `format: junit` | Read JUnit XML from pytest, Maven, or similar tools; require real tests, unique IDs, and consistent counts; failures, skips, and missing evidence do not pass |
| `format: unittest` | Read execution results from this skill's `test_runner.py` |
| `format: checks` | Read assertions from a trusted deterministic evaluator, such as `{"checks":[{"id":"goal-id","result":"PASS"}]}`; each assertion needs a unique ID |

Every format requires execution evidence. Exit code 0 alone is insufficient.

### Databases and temporary services

Use the project's PostgreSQL/MySQL, message broker, containers, or fixtures. Add migration, rollback, idempotency, or concurrency jobs when the change calls for them. Business consistency requirements determine transaction boundaries.

Declare temporary services in `services`. Each entry has id, start, optional ready, stop, and timeout; commands are argv arrays. start returns the startup result, ready waits for availability, and the runner closes services it successfully started in a finally block, including after test failures. Use resource names unique to the task, and have stop clean up only those resources.

Container adapters must generate and export fresh evidence from inside the container. Service faults, timeouts, no tests, and skips produce FAIL, with separate reasons for environment, execution, and assertion problems.

## Save a baseline, then verify the candidate

Fix the goals, allowed changes, protected acceptance files, and test entry points before saving a baseline. After the refactoring, verify the candidate using the same configuration:

```bash
python3 SKILL_DIR/scripts/project.py baseline \
  --project /absolute/project --config /absolute/acceptance.json \
  --output /absolute/evidence/before

python3 SKILL_DIR/scripts/project.py verify \
  --project /absolute/project --config /absolute/acceptance.json \
  --baseline /absolute/evidence/before \
  --output /absolute/evidence/after
```

The output directory must be new and outside tracked sources. A baseline records source hashes, protected tests, configuration and evaluator fingerprints, and actual regression results. Include external acceptance scripts and official test patches through absolute paths in `evaluator_files`. Changes to configuration, protected tests, or the evaluator require a new matching baseline.

`verify` checks that the baseline passed, a real change exists, changes stay in scope, tests remain protected, architecture constraints and goals are met, old regressions still pass, and sources and acceptance material remain unchanged during execution. It reports PASS/FAIL with individual reasons.

### Describe the refactoring goals

Available goal types are `file_exists/file_absent`, `symbol_exists/symbol_absent`, `calls/no_calls`, and `docstring`. Symbols follow the class/function hierarchy within a file. `calls` checks syntactic call names; behavior tests establish branch reachability and dynamic dispatch. Use an external deterministic evaluator for more complex goals and include it in the fingerprints.

### Work with existing architecture debt

`architecture_policy: strict` requires all static constraints in the declared scope to pass. `no_new_violations` records existing baseline findings and rejects new violations; inherited findings remain visible. Choose the scope and policy before refactoring.

Work toward the current business goal in small steps. Keep or remove old entry points according to compatibility agreements. For database changes, record read/write compatibility across intermediate versions and the recovery path. Source fingerprints and subprocesses detect accidental changes; the environment must still trust the project code.

Exit code 0 means PASS; 1 means acceptance completed with unmet conditions; 2 means configuration or runner failure prevented completion. The latter two both produce FAIL with reasons. Design review addresses domain boundaries and pattern choices.
