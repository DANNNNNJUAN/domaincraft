# Releasing

[简体中文](releasing.md) · English

A release has three steps: select the files, validate the installation archive, and upload to GitHub. The local tools handle the first two.

## Build and check

Update `VERSION`, both README versions, and both changelogs, then review `release-files.txt`. Include both language versions of new documentation. Keep the root and installed-skill MIT licenses identical.

```bash
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist
python3 -B tools/verify_release.py dist/ddd-python-skill-0.1.0.zip
```

Use the version from `VERSION` in the archive name. The ZIP contains the repository files and a generated `RELEASE-MANIFEST.json` with a SHA-256 hash for every file. The adjacent `.sha256` file checks the entire archive. File order and timestamps are fixed, so identical inputs are reproducible in the same Python/zlib environment.

The verifier checks paths, the file list, and hashes before extracting to a temporary directory. It then runs the installer, tool self-tests, order example, and release-tool tests. It also checks that reinstalling preserves existing files, and reports PASS/FAIL. Hashes check content integrity, not publisher identity. Verification executes code from the archive, so use an archive you built or trust.

## Upload to GitHub

After creating a repository, upload the extracted files or push the local repository. Check the scope with `git status`: `benchmarks/`, `validation/`, and `dist/` should be ignored. Match the tag to the version, for example `v0.1.0`.

Wait for CI to pass, then create a Release with the ZIP and `.sha256` file attached. The workflow follows [GitHub's Python matrix approach](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), with Actions pinned to specific commits. Passing status comes from the actual remote runs.

## Preserve experiment records

Machine-specific benchmark configuration, source trees, and raw logs stay in the development workspace. Publishing a separate reproducible experiment requires download instructions, environment setup, license handling, and a fresh baseline in that environment.
