# Contributing

[简体中文](CONTRIBUTING.md) · English

Use Python 3.9+. The tools and their tests depend only on the standard library.

## Changes and tests

Start with a business requirement or a reproducible problem. Explain who maintains the rule before choosing objects, interfaces, or patterns. Comments should explain business reasons, contracts, and consistency requirements.

When changing a checker, add both a valid case and a case that exposes the defect. Keep existing assertions and acceptance conditions intact, and report skipped tests. Tests run in temporary directories. Preserve historical experiment records and save new results separately.

Before submitting:

```bash
python3 -B ddd-python/scripts/check.py --self-test
python3 -B ddd-python/scripts/check.py --all
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist
python3 -B tools/verify_release.py dist/ddd-python-skill-0.1.1.zip
```

## Documentation and release files

Maintain documentation in pairs: the original filename holds Chinese, and `.en.md` holds English. Commands, configuration fields, and acceptance conclusions must agree. Write the prose naturally in each language. Keep the MIT license in its original English text.

Add new distribution files to `release-files.txt`. The installed skill should work on its own, with its scripts, references, and examples inside `ddd-python/`. Leave temporary directories, API keys, and local experiment files out of the release list.

A pull request should explain the problem, the resulting behavior, and the validation you actually ran. State any untested environment plainly. Contributions are submitted under this repository's MIT license; third-party content requires the appropriate distribution rights.
