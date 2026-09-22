# Validation record: 0.1.1

[简体中文](validation.md) · English

The core tests, installation checks, and four large-project pilot tasks passed for this release. This record explains what ran, where it ran, and how one of the refactorings changed the code.

## Tests included in the release

| Area | Coverage | Result |
|---|---|---|
| Checkers and project tools | 87 regression tests covering injected defects, package dependencies, baseline protection, service cleanup, and false-PASS detection | PASS |
| Order example | 14 business and repository contract tests, including in-memory and SQLite implementations | PASS |
| Release tools | 6 tests covering archive scope, reproducible builds, symlinks, altered hashes, and installation protection | PASS |

Clean installation passed on macOS arm64 with Python 3.9.6 and 3.13.9. The verifier extracts the release into a temporary directory, installs it under a path containing spaces, and runs tests from outside the repository. It also checks that reinstalling preserves existing files.

```bash
python3 -B tools/build_release.py --output dist
python3 -B tools/verify_release.py dist/ddd-python-skill-0.1.1.zip
```

GitHub Actions is configured for additional platforms and Python versions. Their passing status requires actual remote runs.

## Package-layout correction in 0.1.1

User review exposed project-relative module naming and unresolved imports being omitted from architecture checks. This release adds explicit import-root mappings and separate configuration locations, and makes unresolved dependencies fail the check.

Eighteen new regressions cover normal packages, src and namespace layouts, relative imports, nested configuration, visible dependency edges, unknown and out-of-scope imports, and symlink protection. The end-to-end package fixture also runs the existing 14 order tests with qualified imports while preserving comment and rule-trace checks. These are reproduction fixtures; the user's original project was not available for rerunning.

## Large-project pilot runs

These historical pilot results belong to 0.1.0 and were not rerun for this checker fix. One task was selected from each source. These results come from the development workspace. Upstream source trees, containers, and raw logs remain local and are not included in the first release.

| Source | Change and environment | Result |
|---|---|---|
| SWE Atlas / SimpleLogin | Extract domain-deletion scheduling; native tests, PostgreSQL, Redis | PASS |
| SWE-PolyBench / Keras | Consolidate saving logic in the saving API; selected saving tests | PASS |
| SWE-bench Pro / Open Library | Move the shared conversion function, then fix dropped author-statement and page-count fields | PASS |
| ScarfBench / PetClinic | Extract shared lookup logic in a locally adapted task; Spring, JPA, H2 | PASS |

Open Library initially returned **FAIL**: forcing two upstream xfail cases to execute exposed failing assertions. After the business fixes, the original threshold and official assertions stayed intact, and `--runxfail --reruns 0` produced PASS. There were 13 regression tests and 41 acceptance tests, with overlap between the groups. This result includes bug fixes beyond the function relocation. The initial FAIL record is preserved.

The separate benchmark runner also passed 21 regression tests in the development workspace. It remains with the experiment materials and is not required to install the skill.

## Before and after: extracting domain-deletion scheduling

This example comes from SWE Atlas / SimpleLogin, task `task-69391d8d1ce51c407be1e533`, at source commit `7bdafc5974898fe05b5d80d0999218aa47ca58f8`.

When a user requests deletion, the application marks the domain as pending deletion, creates a background job containing its ID, and tells the user that deletion is scheduled. The refactoring moves that operation into `delete_custom_domain` in `app/custom_domain_utils.py`, preserving the job arguments and existing commit behavior.

The following pseudocode was written from the actual patch to show the flow. It omits logging, authorization checks, and other branches. `create_deletion_job` represents the actual `Job.create(...)` call; `deletion_notice` represents the page message and response.

### Before

The page controller changes the state, creates the job, and prepares the response:

```python
def domain_detail(domain):
    domain.pending_deletion = True
    create_deletion_job(domain.id, run_at=now(), commit=True)
    return deletion_notice(domain)
```

### After

The state change and job creation move together into a function that the controller calls:

```python
def delete_custom_domain(domain):
    # Preserve the existing joint commit of the pending flag and job.
    domain.pending_deletion = True
    create_deletion_job(domain.id, run_at=now(), commit=True)


def domain_detail(domain):
    delete_custom_domain(domain)
    return deletion_notice(domain)
```

“Schedule deletion” is a complete business operation, which gives the extraction a clear boundary. `CustomDomain` and `Job` continue to represent the existing state and persistence behavior. The controller focuses on the page flow, applying SRP through a concrete responsibility split. A function is enough for this change.

The new function still depends on the project's ORM and job model. Its comment explains why the commit behavior stays together; tests check the resulting state and calls.

### Acceptance results

| Check | Before | After |
|---|---|---|
| Existing domain-utility regressions | PASS, 14 tests | PASS, the same 14 tests |
| Separate deletion operation | Absent in the original source | PASS, `delete_custom_domain` exists |
| Controller delegation | Creates the job directly | PASS, calls the new operation and no longer creates `Job` directly |
| Deletion-specific tests | Not run during baseline capture | PASS, covering the pending flag, job contents, return value, and already-pending input |
| Change scope and test protection | Baseline and protected files recorded | PASS, changes stay in scope and upstream tests are unchanged |

Acceptance ran 18 tests, including the original 14 regressions, with PostgreSQL and Redis. The final result was **PASS**. New tests that were not run during baseline capture remain recorded as not run.

Development evidence lives at `benchmarks/large/patches/atlas.patch`, `benchmarks/large/results/atlas-baseline-final/`, and `benchmarks/large/results/atlas-after/`. These paths belong to the local experiment directory excluded from the release.

## Interpreting the results

These records validate the selected implementations and acceptance workflow. Atlas used executable tests without its LLM rubric. PetClinic used a locally adapted task without the official ScarfBench framework migration. The four runs had no controlled with-skill/without-skill comparison, so they do not establish a causal improvement from the skill.

Static architecture analysis covers Python. Runtime and shared-data relationships are declared in configuration. Domain boundaries, responsibilities, and pattern costs still require business review; an automated PASS means the declared executable conditions were met.
