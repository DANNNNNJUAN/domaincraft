# 接入多包项目并验收重构

简体中文 · [English](large-projects.en.md)

已有 Python 项目可以通过 `scripts/project.py` 接入自己的测试环境，按 inspect、baseline、verify 三个阶段做局部重构。`check.py` 继续负责模型关联和注释检查。工具本身使用标准库，不调用大模型 API；项目依赖由项目环境提供。

## 先把范围说清楚

读取构建配置、包清单、测试配置和迁移入口，确认哪些文件对应哪些 Python 导入名。保留项目现有的业务语言、公开接口和事务约定，再确定这次改造的边界。

下面是版本 2 的配置示例：

```json
{
  "version": 2,
  "packages": [
    {
      "name": "orders",
      "root": "packages/orders",
      "imports": [{"path": "packages/orders/src", "prefix": ""}],
      "public": ["orders.api"],
      "allow": ["stock"],
      "external": ["typing_extensions"],
      "forbidden": ["sqlite3", "psycopg"]
    },
    {
      "name": "stock",
      "root": "packages/stock",
      "imports": [{"path": "packages/stock/src", "prefix": ""}],
      "public": ["stock.api"],
      "allow": [],
      "external": ["sqlalchemy", "psycopg"]
    }
  ],
  "tracked_paths": ["."],
  "exclude": [".venv/**", "build/**", ".pytest_cache/**"],
  "protected_paths": ["tests/**/*.py", "pyproject.toml"],
  "allowed_changes": ["packages/orders/src/orders/service.py"],
  "architecture_policy": "strict",
  "runtime_edges": [
    {"from": "orders", "to": "stock", "kind": "event", "evidence": "OrderPlaced event subscription in bootstrap.py"}
  ],
  "data_resources": [
    {"name": "stock_table", "readers": ["orders"], "writers": ["stock"], "paths": ["migrations/**"], "evidence": "Stock table ownership and migration manifest"}
  ],
  "goals": [
    {"id": "delegation", "kind": "calls", "path": "packages/orders/src/orders/service.py", "symbol": "place_order", "callee": "stock.reserve"}
  ],
  "jobs": [
    {"id": "regression", "phase": "both", "format": "junit", "argv": [".venv/bin/python", "-m", "pytest", "tests", "--junitxml={evidence}"], "cwd": ".", "timeout": 600}
  ]
}
```

### 包映射和依赖

`imports.path` 相对项目根目录。空 `prefix` 下，`src/acme/orders.py` 解析为 `acme.orders`；如果映射直接指向 `orders/`，则使用 `prefix: orders`。重复导入名会被拒绝。导入名与发行包名可以不同，发行版本冲突仍交给项目的依赖管理工具处理。

`public` 列出其他包可导入的模块前缀，`allow` 列出可依赖的包名；同包内部引用不受 `public` 限制。普通、相对和条件导入都会进入静态图，检查模块环与包环。外部库显式列在 `external`，未知导入和通配导入会产生检查结果。运行检查器的 Python 必须能解析项目语法。

### 文件范围

静态分析覆盖配置中的源码。将相关数据、配置和迁移文件纳入 `tracked_paths`，才能检测它们的变化。通常追踪整个项目，再排除构建产物；`.git`、`__pycache__` 和 `.pyc` 默认忽略。

标记为 `language: "native"` 的包参加修改范围和原生测试验收，无需 Python 导入映射，也不进行 Java/JavaScript 静态架构检查。符号链接应在独立工作副本中物化并记录处理方式，原项目链接保持原样。

## 查看变更影响

```bash
python3 SKILL_DIR/scripts/project.py inspect \
  --project /absolute/project --config /absolute/acceptance.json \
  --changed packages/stock/src/stock/api.py \
  --output /absolute/evidence/inspection
```

报告会列出导入关系、传递受影响包、声明的事件/RPC/配置关系，以及共享数据的读写参与者。运行时和数据关系由可核查的项目资料提供；共享资源按保守的双向关系传播影响。

未知文件变化、无法解析的导入或动态加载，会把影响范围扩大到全部配置包。动态导入默认导致失败；有依据的例外可在 `dynamic_import_exceptions` 中填写 module 和 reason，同时声明运行时关系。例外会保留在报告中，并要求全范围验证。

影响图用于解释范围。`verify` 始终运行配置中的全部 jobs，不会根据图自动跳过测试。

## 运行项目自己的测试

每个 job 的 `argv` 是参数数组，直接启动进程。支持 `{python}`、`{project}`、`{skill}`、`{artifacts}`、`{evidence}` 占位符。`cwd` 位于项目内，`env` 可传入测试配置；密码和生产连接应由环境提供，避免写入配置文件。

| 配置 | 含义 |
|---|---|
| `phase: both` | 基线和候选都运行，候选必须保留原先通过的测试 ID |
| `phase: after` | 只在候选阶段运行新增需求或重构目标验收 |
| `format: junit` | 读取 pytest、Maven 等产生的 JUnit XML，要求真实测试记录、唯一 ID 和一致的数量；失败、跳过、缺失均不通过 |
| `format: unittest` | 读取本 Skill 的 `test_runner.py` 执行结果 |
| `format: checks` | 读取可信确定性验证器产生的断言结果，例如 `{"checks":[{"id":"goal-id","result":"PASS"}]}`，每条断言有唯一 ID |

所有格式都需要实际证据，只有退出码 0 不足以通过。

### 数据库和临时服务

沿用项目的 PostgreSQL/MySQL、消息代理、容器或测试夹具。根据改造内容添加迁移、事务回滚、幂等或并发测试 job，事务边界由业务一致性需求决定。

临时服务放进 `services` 数组。每项包含 id、start、可选 ready、stop 和 timeout，命令均为 argv 数组。start 返回启动结果，ready 等待服务可用，运行器在 finally 中关闭本次成功启动的服务，测试失败时也执行清理。使用本任务独有的资源名，stop 只清理这些资源。

容器适配器应在容器内生成新的证据并导出。服务故障、超时、没有测试和跳过都记为 FAIL，报告中区分环境、执行与断言原因。

## 保存基线，再验证候选

先固定目标、允许修改的文件、受保护验收文件和测试入口，再保存基线。完成改造后，用同一配置验证候选：

```bash
python3 SKILL_DIR/scripts/project.py baseline \
  --project /absolute/project --config /absolute/acceptance.json \
  --output /absolute/evidence/before

python3 SKILL_DIR/scripts/project.py verify \
  --project /absolute/project --config /absolute/acceptance.json \
  --baseline /absolute/evidence/before \
  --output /absolute/evidence/after
```

输出目录必须是新目录，放在被追踪源码之外。基线保存源码摘要、受保护测试、配置和执行器指纹，以及真实回归结果。外部验收脚本和官方测试补丁通过 `evaluator_files` 的绝对路径列表一起固定。修改配置、受保护测试或执行器后，需要重新建立匹配的基线。

`verify` 检查基线是否成功、是否有真实改动、修改是否越界、测试是否受保护、架构约束和目标是否满足、原回归是否保持，以及运行期间源码和验收是否变化。最终给出 PASS/FAIL 和逐项原因。

### 描述重构目标

可用的目标类型是 `file_exists/file_absent`、`symbol_exists/symbol_absent`、`calls/no_calls` 和 `docstring`。符号按文件内的类/函数层级定位。`calls` 检查语法中的调用名称，分支可达性和动态派发由行为测试验证。复杂目标可交给外部确定性验证器，并把它纳入指纹记录。

### 处理遗留架构问题

`architecture_policy: strict` 要求声明范围内的静态约束全部通过。`no_new_violations` 则保存基线已有问题，要求候选不新增违规，报告仍列出继承的问题。范围和政策在重构前确定。

按当前业务目标逐步改造，旧入口的保留或移除遵循兼容性约定。涉及数据库结构时，记录中间版本的读写兼容和恢复路径。源码指纹与子进程用于发现误改，运行环境仍需信任项目代码。

退出码 0 表示 PASS；1 表示验收完成但有条件未满足；2 表示配置或运行器未能完成。后两种结果都为 FAIL，并保留原因。领域边界和模式取舍由设计评审判断。
