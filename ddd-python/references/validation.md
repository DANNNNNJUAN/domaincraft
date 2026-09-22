# 运行本地检查

简体中文 · [English](validation.en.md)

`check.py` 检查模型关联、架构、注释和业务测试。多包项目或项目原生测试使用[项目验收入口](large-projects.md)。两种入口都保留实际执行证据。

Python 3.9+ 标准库即可运行以下命令，无需 pytest、网络或 API Key。使用绝对路径时，可以从任意目录执行。包映射和放在子目录的配置文件见[布局配置](model-format.md)。

```bash
python3 /absolute/ddd-python/scripts/check.py --all
python3 /absolute/ddd-python/scripts/check.py --project /absolute/project --model --comments
python3 /absolute/ddd-python/scripts/check.py --project /absolute/project --architecture
python3 /absolute/ddd-python/scripts/check.py --project /absolute/project --tests --timeout 60
python3 /absolute/ddd-python/scripts/check.py --self-test
```

`--all` 包括包完整性、模型、架构、注释和业务测试，也是未指定选项时的默认行为。`--self-test` 单独运行工具回归。使用 `--json PATH --markdown PATH` 保存报告。

## 读懂结果

| 退出码 | 含义 |
|---|---|
| 0 | 所选自动检查通过 |
| 1 | 规则不满足，或测试失败、跳过导致证据不足 |
| 2 | 输入、配置、语法或运行器故障 |

`semantic_status` 单独记录语义评审状态，待评审本身不会让退出码变成非零。未选择的检查显示 `not_run`。报告还会列出通过、失败、跳过和需评审的具体项目。

测试使用当前 Python 在独立子进程中执行，默认超时 60 秒，并捕获 Python 标准输出和错误。没有测试、发现失败、运行器故障、超时或跳过都不能作为通过证据。子进程仍会执行项目代码，应使用可信的测试环境。

## 检查内容

| 检查 | 自动验证的内容 | 需要进一步判断的内容 |
|---|---|---|
| 模型关联 | 编号、引用、规则归属、实现符号和测试关联 | 业务假设是否成立 |
| 静态架构 | 配置范围内的导入、禁止模块、层间依赖和模块环 | 其他反射行为及声明范围是否完整 |
| 注释结构 | 文档存在、Rules 引用、Args 参数名 | 注释是否准确解释业务 |
| 业务执行 | 断言、异常、拒绝后状态、仓储契约和 SQLite 集成 | 测试是否覆盖关键业务场景 |

报告中的 `source_roots` 说明静态覆盖范围。领域边界、SOLID 的适用方式和模式取舍由设计评审确认。

## 编写回归测试

先根据已确认的需求写黑盒断言，再用正常用例和缺陷注入检查工具是否工作。随包测试覆盖不变量、状态转换、非法输入拒绝、值对象和多适配器契约。

工具测试使用临时目录，注入悬空引用、非法导入、循环、失效注释和错误业务行为。判断依据是实际行为和退出状态。Skill 的自然语言设计能力则需要通过具体使用任务单独评估。
