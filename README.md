# DomainCraft

简体中文 · [English](README.en.md)

把业务规则写进对象，再用测试确认它们没有在实现和重构中走样。

DomainCraft 是一个面向 Python 的 DDD Skill。它从业务语言、聚合边界和不变量出发，帮助你分配对象职责、选择合适的实现方式，并运行本地检查。当前版本为 **0.1.0 预览版**，安装名和调用名仍为 `ddd-python`。

## 适合用在哪里

你可以用它从需求开始设计领域模型，也可以接手已有项目，先固定当前行为，再逐步重构。它会把业务规则与实现、注释、测试关联起来，检查多包依赖，并通过项目自己的测试验收改动。

这里的 DDD、OOP、SOLID 和设计模式有各自的工作：DDD 帮助确定业务边界，对象负责维护边界内的规则，SOLID 用来审视职责和协作，模式则按具体问题选择。简单的业务操作，用一个清楚的方法或函数就够了。

验证脚本只依赖 **Python 3.9+ 标准库**，不调用大模型 API。目标项目需要的数据库、测试框架和其他依赖，仍由项目自己的环境提供。最终验收给出 **PASS/FAIL** 和原因。

## 安装和使用

下载并解压发布包，或克隆仓库，然后在仓库根目录运行：

```bash
python3 tools/install_skill.py
```

默认位置是 `${CODEX_HOME:-~/.codex}/skills/ddd-python`。需要安装到其他位置时：

```bash
python3 tools/install_skill.py --skills-dir /absolute/path/to/skills
```

安装器会复制完整的 Skill，遇到已有目录就停止。升级前请备份并移走旧版本；旧版本生成的验收基线应与旧脚本一起保留。

在已加载 Skill 的 Codex 会话中，可以这样提问：

> 使用 $ddd-python，根据订单确认规则设计领域对象。说明谁负责维护不变量，写出 Python 实现、必要注释和测试，然后执行验证。

> 使用 $ddd-python，重构这个多包项目中的订单流程。先保存行为基线和验收目标，再修改代码，最后给出 PASS/FAIL 和测试证据。

完整的[设计指导](ddd-python/SKILL.md)和[英文指导](ddd-python/SKILL.en.md)都包含在安装包中。

## 先跑一个例子

在仓库根目录执行：

```bash
python3 -B ddd-python/scripts/check.py --all
python3 -B ddd-python/scripts/check.py --self-test
```

第一条检查随包的订单示例，包括内存和 SQLite 仓储契约。第二条运行工具自身的回归测试。

接入自己的项目时，按需要选择入口：

| 你想做的事 | 使用方式 |
|---|---|
| 关联业务规则、对象职责、注释与测试 | 使用 `check.py`，提供 `model.json`、`architecture.json` 和 unittest 测试；见[格式说明](ddd-python/references/model-format.md) |
| 验收已有多包项目或数据库相关改造 | 使用 `project.py inspect/baseline/verify`，配置源码范围、依赖和原生测试命令；见[项目接入](ddd-python/references/large-projects.md) |

报告和基线放在被测源码目录之外。候选代码与基线比较时，配置、受保护测试和验收器必须保持一致。

## 验证到了什么程度

核心有 69 项工具回归、14 项订单示例测试和 6 项发布工具测试。干净安装已在 macOS arm64 的 Python 3.9.6 和 3.13.9 上通过。[验证记录](docs/validation.md)列出了大型项目试跑，并展示了一个实际的改造前后样例。

自动检查负责声明范围内的依赖、代码结构和测试结果；领域边界是否合理、模式是否值得采用，仍需结合业务评审。`check.py` 会单独记录 `semantic_status`。数据库迁移、并发和外部服务行为，需要项目提供相应测试。

Python 之外的项目可以接入原生测试，静态架构分析目前只支持 Python。Windows 尚未验证。GitHub Actions 已配置 Linux 的 Python 3.9/3.11/3.13 和 macOS 的 Python 3.11，远程结果以实际运行记录为准。验证器会执行项目代码，请在可信的测试环境中运行。

## 开发与发布

```bash
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist
python3 -B tools/verify_release.py dist/ddd-python-skill-0.1.0.zip
```

发布内容由 `release-files.txt` 逐项列出。大型 benchmark 的上游源码、容器和原始实验记录留在开发工作区，由 Git 忽略，安装 Skill 时不需要它们。

[贡献说明](CONTRIBUTING.md) · [更新记录](CHANGELOG.md) · [发布流程](docs/releasing.md) · [来源说明](THIRD_PARTY_NOTICES.md)

自有代码、文档和示例采用 [MIT 许可证](LICENSE)。第三方材料保留各自的许可。
