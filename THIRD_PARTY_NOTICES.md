# 第三方来源

简体中文 · [English](THIRD_PARTY_NOTICES.en.md)

发布包包含本项目的 Skill、工具、示例、测试和文档。开发时用到的第三方 benchmark 源码、候选副本、官方测试补丁和容器镜像保留在本地实验目录。

## 开发试跑来源

| 来源 | 使用范围 |
|---|---|
| [Cosmic Python](https://github.com/cosmicpython/code) | 固定提交 `3e9871d62fb813d5206c0698974bdb54339fad6a` |
| [RefactorBench](https://github.com/microsoft/RefactorBench) | 固定提交 `210b2d15a373ad265aa721f70199c9962d7de069`，涉及 Requests 和 Flask |
| [SWE Atlas](https://github.com/scaleapi/SWE-Atlas) | SimpleLogin 的一个任务 |
| [SWE-bench Pro](https://github.com/scaleapi/SWE-bench_Pro-os) | Open Library 的一个任务 |
| [SWE-PolyBench](https://github.com/amazon-science/SWE-PolyBench) | Keras 的一个任务 |
| [ScarfBench](https://github.com/scarfbench/benchmark) | 基于 PetClinic 的本地改编重构任务 |

这些名称用于记录来源，不代表上游对本项目的背书。原始许可、固定源码和详细记录保留在开发工作区。另行分发这些材料时，应逐项核对上游许可；本项目的 MIT 许可证只适用于自有内容。

## CI 依赖

GitHub Actions 工作流引用固定提交的 [checkout](https://github.com/actions/checkout) 和 [setup-python](https://github.com/actions/setup-python)。这两个 Action 的源码没有捆绑进发布包，适用各自许可证。
