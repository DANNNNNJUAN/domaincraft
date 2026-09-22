# Third-party sources

[简体中文](THIRD_PARTY_NOTICES.md) · English

The release contains this project's skill, tools, examples, tests, and documentation. Third-party benchmark sources, candidate copies, official test patches, and container images used during development stay in the local experiment directory.

## Development pilot sources

| Source | Scope used |
|---|---|
| [Cosmic Python](https://github.com/cosmicpython/code) | Commit `3e9871d62fb813d5206c0698974bdb54339fad6a` |
| [RefactorBench](https://github.com/microsoft/RefactorBench) | Commit `210b2d15a373ad265aa721f70199c9962d7de069`, including Requests and Flask tasks |
| [SWE Atlas](https://github.com/scaleapi/SWE-Atlas) | One SimpleLogin task |
| [SWE-bench Pro](https://github.com/scaleapi/SWE-bench_Pro-os) | One Open Library task |
| [SWE-PolyBench](https://github.com/amazon-science/SWE-PolyBench) | One Keras task |
| [ScarfBench](https://github.com/scarfbench/benchmark) | A local refactoring task adapted from PetClinic |

These names identify sources, not upstream endorsements. Original licenses, pinned sources, and detailed records remain in the development workspace. Check each upstream license before redistributing those materials. This project's MIT license applies to its original content.

## CI dependencies

The GitHub Actions workflow references pinned commits of [checkout](https://github.com/actions/checkout) and [setup-python](https://github.com/actions/setup-python). Their source code is not bundled in the release, and each retains its own license.
