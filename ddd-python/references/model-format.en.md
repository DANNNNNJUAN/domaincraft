# Model and architecture configuration: v1

[简体中文](model-format.md) · English

`model.json` connects business rules, responsibilities, decisions, and tests. Treat it as the source of those links and reference the same IDs in other documents. File paths are relative to the project root; absolute paths and paths escaping the root are rejected. JSON keeps the runtime dependency-free.

See [model.json](../assets/order_example/model.json) for a complete example.

## model.json fields

| Field | Requirement |
|---|---|
| version | Integer `1` |
| contexts | Nonempty array; each entry has nonempty id, name, and responsibility strings |
| aggregates | Each entry has id, context, root, and invariants; root is a Python class symbol and invariants is a nonempty array of rule IDs |
| rules | Nonempty array; IDs such as `ABC-001`; kind is invariant or contract; includes statement, source, status, owner, symbols, and tests; status is confirmed or assumption |
| decisions | Each entry has id, problem, evidence, choice, alternatives, reason, consequences, solid, verification, and rules; rules may be empty for a purely architectural decision |
| responsibilities | Each entry has symbol, responsibility, rules, and decisions; link at least one rule or decision |
| reviews | Nonempty list of questions requiring semantic review |

IDs must be unique within each collection. An `invariant` rule and its aggregate's invariant list must reference each other. A `contract` represents interface or persistence behavior; describe its ownership through responsibilities rather than listing it as an aggregate invariant.

`owner` identifies the aggregate with primary domain ownership. `responsibilities` identifies the object that maintains the contract, including storage-adapter responsibilities. Name the coordinator for a cross-aggregate workflow and explain the choice in a decision.

`symbols` references implementations such as `domain.order.Order.confirm`. `tests` uses complete unittest IDs such as `tests.test_order.OrderTests.test_empty_order`. Symbols must resolve to modules, classes, or functions found in the AST; dynamically generated definitions need separate review. With `--tests`, the checker verifies actual outcomes for linked tests. Skipped, missing, or unexecuted tests cannot pass.

## architecture.json

```json
{
  "source_roots": ["domain", "application", "infrastructure"],
  "layers": [
    {"prefix": "domain", "allow": ["domain"], "forbidden": ["sqlite3"]},
    {"prefix": "application", "allow": ["application", "domain"], "forbidden": []},
    {"prefix": "infrastructure", "allow": ["infrastructure", "domain"], "forbidden": []}
  ],
  "exceptions": [],
  "test_dir": "tests"
}
```

Internal modules belong to the layer with the longest matching prefix. `allow` lists permitted layer prefixes; `forbidden` matches a module and its submodules. Ordinary, from, relative, and conditional imports enter the static graph, including `TYPE_CHECKING` branches, and are checked for module cycles. Detected dynamic and wildcard imports fail the check; other reflection or plugin behavior needs project-specific acceptance.

A composition root can declare a specific dependency exception:

```json
{"from":"application.bootstrap","to":"infrastructure.memory","decision":"DEC-001","reason":"The composition root wires adapters"}
```

The exception must refer to real modules and an existing decision. It exempts only that dependency edge, remains marked for review, and leaves cycle checking in place.

Comment checking covers `source_roots`: nonempty modules need module documentation, and public classes and methods need docstrings. A class docstring can cover `__init__`; document private methods as needed. Tests express business intent through rule IDs and method docstrings.

## Package layouts and configuration locations (0.1.1)

`source_roots` selects files to scan; `import_roots` determines their Python names. Configure them separately. This layout keeps model files in place and avoids adding generic names such as `domain` or `application` as top-level import paths:

```text
repository/
  src/acme/domain/
  src/acme/application/
  tests/
  docs/ddd/model.json
  docs/ddd/architecture.json
```

A complete architecture configuration for it is:

```json
{
  "source_roots": ["src/acme/domain", "src/acme/application"],
  "import_roots": [
    {"path": "src", "prefix": ""},
    {"path": "tests", "prefix": "tests"}
  ],
  "layers": [
    {"prefix": "acme.domain", "allow": ["acme.domain"], "forbidden": ["sqlite3"]},
    {"prefix": "acme.application", "allow": ["acme.application", "acme.domain"], "forbidden": []}
  ],
  "external": [],
  "exceptions": [],
  "test_dir": "tests"
}
```

Pass the project root and configuration locations separately:

```bash
python3 /absolute/ddd-python/scripts/check.py \
  --project /absolute/repository \
  --model-file docs/ddd/model.json \
  --architecture-file docs/ddd/architecture.json \
  --model --architecture --comments
```

Configuration paths can be absolute or relative to `--project`. Source, test, and mapping paths within the configuration always remain relative to `--project`, not to the JSON file. An import such as `from ..domain import ...` inside `acme.application` resolves using that package name. Model symbols must use real names such as `acme.domain...` too.

If `--project` points directly to `acme/`, use `{"path":".","prefix":"acme"}` to retain its package name. The default is `{"path":".","prefix":""}`, preserving the original flat example. The most specific overlapping mapping wins. Missing mappings, duplicate mapping paths, and duplicate module names are configuration errors. Scanned files still cannot escape the project root through symlinks.

Mappings only affect static indexing; they neither import the project nor alter `sys.path`. Run tests in the project's installed environment with its normal test entry point. Install a src-layout package according to that project's setup. Use `project.py` for other test frameworks.

### Handling unresolved dependencies

The standard library is recognized by default. Declare third-party module prefixes in `external`, for example `["requests", "sqlalchemy"]`. This declaration does not override `forbidden` or reclassify local code outside the scan scope as third-party code.

Unknown imports produce `ARCH-UNKNOWN-IMPORT`; local dependencies found outside the scan scope produce `ARCH-OUTSIDE-SCOPE`. Unassigned source modules produce `ARCH-UNCLASSIFIED`, and layers matching no source produce `ARCH-EMPTY-LAYER`. Dynamic and wildcard imports produce `ARCH-DYNAMIC` and `ARCH-STAR`. All fail the check. For justified runtime exceptions, use `project.py` with explicit relationships and full-scope acceptance.

The report's `architecture_graph` records resolved source dependency edges. `architecture_imports` lists every import and its classification; `scope` lists mappings, configuration locations, and external prefixes. These let you inspect which edges were actually checked.
