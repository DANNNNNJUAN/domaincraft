# Changelog

[简体中文](CHANGELOG.md) · English

## 0.1.1 — 2026-09-22

Fix module naming for normal Python packages and imports that were silently omitted from architecture checks.

- Add `import_roots` mappings for qualified package names, relative imports, src layouts, and namespace packages.
- Add `--model-file` and `--architecture-file` so configuration can stay inside a package or documentation directory.
- Fail architecture checks on unknown imports, local dependencies outside the scan scope, unmatched layers, dynamic imports, and wildcard imports.
- Require explicit `external` prefixes for third-party imports; recognize the standard library and continue to enforce forbidden dependencies.
- Include `architecture_graph` and individual `architecture_imports` in reports while preserving rule traceability and comment checks.
- Add 18 package-layout and failure-behavior regressions, bringing tool regressions to 87.

When migrating, check package prefixes and declare external dependencies. Rerun earlier checks that passed with unresolved imports.

## 0.1.0 — 2026-09-22

The first DomainCraft preview brings domain design and local acceptance testing into one Python workflow.

- Connect business rules to object responsibilities, SOLID review, and pattern selection.
- Check model references, dependencies, comments, and test execution, with in-memory and SQLite order examples.
- Support multiple source roots, package boundaries, dependency cycles, and declared runtime and shared-data dependencies.
- Save refactoring baselines, run native tests and temporary services, and report PASS/FAIL against change scope and concrete goals.
- Include a local installer, reproducible release archive, file hashes, clean-install validation, and GitHub Actions.
- Provide complete Chinese and English documentation, including an actual before-and-after example.

See the [validation record](docs/validation.en.md) for the current environment and coverage.
