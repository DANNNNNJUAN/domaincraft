# 模型与架构配置：v1

简体中文 · [English](model-format.en.md)

`model.json` 把业务规则、对象职责、决策和测试关联在一起。以它作为关联记录的来源，其他文档引用相同编号。文件路径相对项目根目录，绝对路径和越界路径会被拒绝。配置使用 JSON，运行时只需标准库。

完整示例见 [model.json](../assets/order_example/model.json)。

## model.json 字段

| 字段 | 要求 |
|---|---|
| version | 整数 `1` |
| contexts | 非空数组；每项有非空字符串 id、name、responsibility |
| aggregates | 每项有 id、context、root、invariants；root 是 Python 类符号，invariants 是非空规则编号数组 |
| rules | 非空数组；id 如 `ABC-001`；kind 为 invariant 或 contract；包含 statement、source、status、owner、symbols、tests；status 为 confirmed 或 assumption |
| decisions | 每项有 id、problem、evidence、choice、alternatives、reason、consequences、solid、verification、rules；纯架构决策的 rules 可为空 |
| responsibilities | 每项有 symbol、responsibility、rules、decisions；至少关联一条规则或一项决策 |
| reviews | 非空列表，记录待语义评审的问题 |

各集合内的编号必须唯一。`invariant` 规则与聚合的不变量清单双向关联；`contract` 表达接口或持久化契约，放在职责记录中，不放进聚合不变量清单。

`owner` 指向主要领域归属的聚合编号。具体维护契约的对象由 `responsibilities` 说明，包括存储适配器的职责。跨聚合流程应注明协调者，并在决策中解释。

`symbols` 引用实现，例如 `domain.order.Order.confirm`；`tests` 使用完整 unittest 编号，例如 `tests.test_order.OrderTests.test_empty_order`。符号须能在 AST 中找到对应模块、类或函数，动态生成的定义另行评审。开启 `--tests` 后会核对关联测试的实际结果，跳过、未发现或未执行均不能通过。

## architecture.json

```json
{
  "source_roots": ["domain", "application", "infrastructure"],
  "layers": [
    {"prefix": "domain", "allow": ["domain"], "forbidden": ["sqlite3"]},
    {"prefix": "application", "allow": ["application", "domain"], "forbidden": []},
    {"prefix": "infrastructure", "allow": ["infrastructure", "domain"], "forbidden": []}
  ],
  "exceptions": [],
  "test_dir": "tests"
}
```

内部模块按最长前缀归属到层。`allow` 列出可依赖的层前缀，`forbidden` 匹配模块及其子模块。普通、from、相对和条件导入都会进入静态图，包含 `TYPE_CHECKING` 分支，并用于检测模块环。运行时拼接导入、反射和任意插件加载需要单独检查。

装配层可以声明具体的依赖例外：

```json
{"from":"application.bootstrap","to":"infrastructure.memory","decision":"DEC-001","reason":"组合根负责装配适配器"}
```

例外必须对应真实模块和已有决策。它只豁免这一条依赖边，报告仍标为需评审，循环依赖照常检查。

注释检查覆盖 `source_roots`：非空模块需要模块文档，公开类和方法需要文档，`__init__` 可使用类文档。私有方法按需说明。测试通过规则编号和方法 docstring 表达业务意图。
