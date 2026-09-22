---
name: ddd-python
description: Design and incrementally refactor Python domain models and multi-package projects by tracing business invariants to object responsibilities, justified patterns, SOLID contracts, and local PASS/FAIL acceptance. Use for DDD-oriented implementation, architecture checks, and database-backed project validation.
---

# DomainCraft：Python 领域设计与验证

简体中文 · [English](SKILL.en.md)

从业务规则出发设计对象，写出实现，再用可执行测试检查结果。按用户的语言交流，沿用项目的命名、架构和工具习惯。英文任务可使用[英文参考资料](SKILL.en.md)。

## 设计从哪里开始

DDD 负责业务语言、上下文、聚合和不变量。本 Skill 采用 OOP 来组织实现：先确定谁维护规则，再考虑接口、组合和多态。划分聚合时看业务一致性和生命周期，不直接照搬数据库外键。

用 SOLID 检查这些决定：SRP 看变化原因，OCP 看已知的变化需求，LSP 看行为契约，ISP 看调用者需要，DIP 看选定架构中的依赖方向。类的大小、接口的数量只能提供线索。

模式选择跟在具体问题后面。记录变化或协作需求、简单替代方案与成本，再决定是否需要模式。抽取策略、工厂或服务后，要明确不变量由谁维护，并确保每个合法入口都遵守同一契约。

业务简单时保持实现简单。微服务、事件溯源、异步事件和事务边界，都应由一致性需求与架构决策支持。

## 按任务推进

先判断用户需要设计、实现、检查还是重构，只展开相关工作。多包、src 布局、项目自有测试框架或数据库项目，从[项目接入](references/large-projects.md)开始：固定包映射、数据与运行时依赖、修改范围和验收，再做局部改造。

1. **梳理业务规则。**记录来源、确认状态、业务语言、上下文和不变量。尚未确认的规则标为假设。
2. **分配职责。**说明聚合、值对象、应用编排和外部端口如何协作，写清前置条件、结果、异常与一致性边界。参考[对象设计](references/design.md)。
3. **选择实现。**把对象职责关联到业务规则或架构决策，说明采用某种模式的原因、替代方案、SOLID 影响和验证方法。
4. **写代码和注释。**优先使用清楚的组合关系；策略可以是函数，Protocol 用在确有替换需求的边界。注释解释业务原因和契约。参考[订单示例](assets/order_example/model.json)。
5. **建立测试。**根据已确认的规则覆盖正常、边界、拒绝和拒绝后状态保持。多个实现共用契约测试；持久化、并发和幂等需求配套集成测试。
6. **运行并复验。**按[验证说明](references/validation.md)执行，定位失败原因后修改相关代码。保留断言和验收条件，如实记录跳过；同类修复两次仍无进展时，保存失败证据并说明阻塞点。

领域边界、职责划分、模式成本和业务假设需要语义评审。在报告中写清自动检查结果与仍待确认的设计问题。要评估 Skill 的效果，参考[效果评测](references/benchmarking.md)，区分工具自测、参考实现校准和受控实验。

## 运行验证

脚本使用 Python 3.9+ 标准库，不联网、不调用大模型 API，也不安装依赖。把下面的 `SKILL_DIR` 替换为本文件所在目录的绝对路径。

```bash
python3 SKILL_DIR/scripts/check.py --all
python3 SKILL_DIR/scripts/check.py --project /absolute/project --all \
  --json /absolute/output/report.json --markdown /absolute/output/report.md
python3 SKILL_DIR/scripts/check.py --self-test
```

`check.py` 默认检查订单示例。接入自己的项目时，提供 `model.json`、`architecture.json` 和可发现的 unittest 测试，具体见[格式说明](references/model-format.md)。`project.py` 直接接入项目原生测试，无需补写整库模型清单。

重构验收同时检查行为保持和具体目标，最终只给 PASS/FAIL。环境故障、超时、跳过或缺少证据均不能算通过，报告保留各自原因，不输出设计分数。原有测试通过后，还要确认新的重构目标确实完成。

项目测试会执行项目代码，应在可信环境中运行。尽量使用本地夹具替换网络服务，并说明集成测试所需的资源。

## 交付内容

交付实际实现、必要注释和测试，以及业务规则、职责、决策与测试的关联记录。JSON/Markdown 报告保留通过、失败、跳过、未执行和需评审等明细，列出规则编号、位置、证据和建议。

评审批注落到具体代码，说明业务影响。按本次任务提供所需文档，让用户能理解改动并复验结果。
