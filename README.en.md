# DomainCraft

[简体中文](README.md) · English

Put business rules into objects, then use tests to keep them intact as the code changes.

DomainCraft is a DDD skill for Python. It starts with domain language, aggregate boundaries, and invariants, then helps you assign responsibilities, choose an implementation, and check the result locally. The current release is **0.1.1 preview**. Its installation and invocation name remains `ddd-python`.

## Where it helps

Use it to build a domain model from requirements, or to work through an existing project one refactoring at a time. It connects business rules to code, comments, and tests, checks dependencies across packages, and runs the project's own tests to validate changes.

DDD, OOP, SOLID, and design patterns each have a job here. DDD helps define business boundaries. Objects maintain the rules within those boundaries. SOLID helps review responsibilities and collaboration. Patterns are chosen for a concrete problem. A straightforward method or function is often enough.

The validation scripts use only the **Python 3.9+ standard library** and make no LLM API calls. The target project supplies its own database, test framework, and other dependencies. Acceptance results are **PASS/FAIL**, with reasons.

## Install and use

Download and extract a release, or clone the repository, then run from its root:

```bash
python3 tools/install_skill.py
```

The default destination is `${CODEX_HOME:-~/.codex}/skills/ddd-python`. To choose another location:

```bash
python3 tools/install_skill.py --skills-dir /absolute/path/to/skills
```

The installer copies the complete skill and stops if the destination already exists. Before upgrading, back up and move the old installation. Keep old acceptance baselines with the scripts that produced them.

In a Codex session with the skill loaded, try:

> Use $ddd-python to model the order confirmation rules. Explain which object maintains each invariant, implement the Python code, comments, and tests, then run validation.

> Use $ddd-python to refactor the order workflow in this multi-package project. Save a behavior baseline and acceptance goals before editing, then report PASS/FAIL with test evidence.

Both the [English guide](ddd-python/SKILL.en.md) and [Chinese guide](ddd-python/SKILL.md) are included in the installation.

## Try the example

From the repository root:

```bash
python3 -B ddd-python/scripts/check.py --all
python3 -B ddd-python/scripts/check.py --self-test
```

The first command checks the bundled order example, including its in-memory and SQLite repository contracts. The second runs the tools' regression tests.

For your own project, choose the entry point that fits the work:

| What you need | Entry point |
|---|---|
| Trace business rules to responsibilities, comments, and tests | Use `check.py` with `model.json`, `architecture.json`, and unittest tests; see the [format guide](ddd-python/references/model-format.en.md) |
| Validate changes in an existing multi-package or database-backed project | Use `project.py inspect/baseline/verify` with source mappings, dependencies, and native test commands; see [project integration](ddd-python/references/large-projects.en.md) |

Keep reports and baselines outside the source tree under test. When comparing a candidate with its baseline, the configuration, protected tests, and evaluator must remain unchanged.

## What has been checked

The core has 87 tool regression tests, 14 order example tests, and 6 release-tool tests. Clean installation has passed on macOS arm64 with Python 3.9.6 and 3.13.9. The [validation record](docs/validation.en.md) also covers large-project pilot runs and walks through an actual before-and-after refactoring.

Automated checks cover declared dependencies, code structure, and test results. Domain boundaries and the cost of a pattern still need business review; `check.py` records that separately as `semantic_status`. Database migrations, concurrency, and external services need project-specific tests.

Other languages can use the native test runner; static architecture analysis currently supports Python. Windows has not been validated. GitHub Actions is configured for Python 3.9/3.11/3.13 on Linux and Python 3.11 on macOS; remote results depend on the actual workflow runs. The validators execute project code, so run them in a trusted test environment.

## Develop and release

```bash
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist
python3 -B tools/verify_release.py dist/ddd-python-skill-0.1.1.zip
```

`release-files.txt` lists every distributed file. Large benchmark source trees, containers, and raw experiment records stay in the development workspace and are ignored by Git. They are not installation dependencies.

[Contributing](CONTRIBUTING.en.md) · [Changelog](CHANGELOG.en.md) · [Releasing](docs/releasing.en.md) · [Sources](THIRD_PARTY_NOTICES.en.md)

Original code, documentation, and examples use the [MIT license](LICENSE). Third-party materials retain their own licenses.
