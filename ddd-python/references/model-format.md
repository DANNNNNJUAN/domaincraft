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

内部模块按最长前缀归属到层。`allow` 列出可依赖的层前缀，`forbidden` 匹配模块及其子模块。普通、from、相对和条件导入都会进入静态图，包含 `TYPE_CHECKING` 分支，并用于检测模块环。检测到的动态导入和星号导入会导致失败；其他反射或插件行为需要项目专用验收。

装配层可以声明具体的依赖例外：

```json
{"from":"application.bootstrap","to":"infrastructure.memory","decision":"DEC-001","reason":"组合根负责装配适配器"}
```

例外必须对应真实模块和已有决策。它只豁免这一条依赖边，报告仍标为需评审，循环依赖照常检查。

注释检查覆盖 `source_roots`：非空模块需要模块文档，公开类和方法需要文档，`__init__` 可使用类文档。私有方法按需说明。测试通过规则编号和方法 docstring 表达业务意图。

## 包布局与配置位置（0.1.1）

`source_roots` 决定扫描哪些文件；`import_roots` 决定它们在 Python 中叫什么。两者分开配置。下面的目录不需要移动模型文件，也不需要给 `domain`、`application` 这些通用名称添加顶层导入路径：

```text
repository/
  src/acme/domain/
  src/acme/application/
  tests/
  docs/ddd/model.json
  docs/ddd/architecture.json
```

对应的完整架构配置可以写为：

```json
{
  "source_roots": ["src/acme/domain", "src/acme/application"],
  "import_roots": [
    {"path": "src", "prefix": ""},
    {"path": "tests", "prefix": "tests"}
  ],
  "layers": [
    {"prefix": "acme.domain", "allow": ["acme.domain"], "forbidden": ["sqlite3"]},
    {"prefix": "acme.application", "allow": ["acme.application", "acme.domain"], "forbidden": []}
  ],
  "external": [],
  "exceptions": [],
  "test_dir": "tests"
}
```

运行时把项目根目录和配置位置分别传入：

```bash
python3 /absolute/ddd-python/scripts/check.py \
  --project /absolute/repository \
  --model-file docs/ddd/model.json \
  --architecture-file docs/ddd/architecture.json \
  --model --architecture --comments
```

配置文件路径可相对 `--project`，也可为绝对路径。配置里的源码、测试和映射路径始终相对 `--project`，不是相对 JSON 文件的位置。`acme.application` 中的 `from ..domain import ...` 会按包名解析；模型符号也应使用 `acme.domain...` 等真实名称。

如果 `--project` 直接指向 `acme/`，使用 `{"path":".","prefix":"acme"}` 即可保留包名。缺省映射是 `{"path":".","prefix":""}`，兼容原有平铺示例。有重叠路径时使用最具体的映射；缺失映射、重复映射路径或重复模块名会报配置错误。扫描文件仍不能通过符号链接逃出项目根。

映射只用于静态索引，不导入项目或改动 `sys.path`。运行测试时使用项目自己的已安装环境和正常测试入口；`src/` 项目的包应按该项目方式安装。不同测试框架通过 `project.py` 接入。

### 未解析的依赖如何处理

标准库默认识别；第三方模块在 `external` 中按前缀声明，例如 `["requests", "sqlalchemy"]`。声明不会豁免 `forbidden`，也不能把扫描范围外的本地代码当作第三方库。

未知导入报 `ARCH-UNKNOWN-IMPORT`，找到但未扫描的本地依赖报 `ARCH-OUTSIDE-SCOPE`。源码没有对应层会报 `ARCH-UNCLASSIFIED`，没有任何源码匹配的层会报 `ARCH-EMPTY-LAYER`。动态导入和星号导入分别报 `ARCH-DYNAMIC`、`ARCH-STAR`；这些情况均返回失败。需要运行时依赖例外时，使用 `project.py` 的显式关系配置和全范围验收。

报告的 `architecture_graph` 保存解析到的源码依赖边，`architecture_imports` 列出每条导入及其分类；`scope` 列出映射、配置位置和外部前缀。可以直接核对这次实际检查了哪些边。
