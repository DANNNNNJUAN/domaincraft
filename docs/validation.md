# 验证记录：0.1.1

简体中文 · [English](validation.en.md)

这一版的核心测试、安装验证和四个大型项目试跑均已通过。下面分别说明测试内容、运行环境，以及一个实际改造的过程。

## 可以随包复验的测试

| 对象 | 测试内容 | 结果 |
|---|---|---|
| 检查器与项目工具 | 87 项回归，覆盖缺陷注入、多包依赖、基线保护、服务清理和伪通过拦截 | PASS |
| 订单示例 | 14 项业务与仓储契约测试，包含内存和 SQLite 实现 | PASS |
| 发布工具 | 6 项回归，覆盖打包范围、重复构建、符号链接、摘要篡改和安装保护 | PASS |

干净安装已在 macOS arm64 的 Python 3.9.6 和 3.13.9 上通过。验证器把发布包解压到临时目录，安装到含空格的路径，再从仓库外运行测试，并确认重复安装会保留已有文件。

```bash
python3 -B tools/build_release.py --output dist
python3 -B tools/verify_release.py dist/ddd-python-skill-0.1.1.zip
```

GitHub Actions 已配置其他平台和 Python 版本；这些环境的通过状态要等远程运行后确认。

## 0.1.1 的包布局修复

使用反馈指出，原检查器按项目相对路径推导模块名，并会略过未解析的导入。本次增加显式导入根映射和独立配置路径，未解析依赖会使检查失败。

新增 18 项回归覆盖普通包、src 和命名空间布局、相对导入、包内配置、可见依赖边、未知及未覆盖导入，以及符号链接保护。完整包夹具还用真实包名运行原有 14 项订单测试，同时保留注释检查和规则追溯。这些是复现夹具，未获得反馈者的原始项目重新运行。

## 大型项目试跑

以下为 0.1.0 的历史试跑结果，本次检查器修复没有重跑这些实验。每个来源选了一个任务。表中结果来自开发工作区，相关上游源码、容器和原始日志留在本地，未放入首版发布包。

| 来源 | 改造与环境 | 结果 |
|---|---|---|
| SWE Atlas / SimpleLogin | 抽取域名删除调度；原生测试、PostgreSQL、Redis | PASS |
| SWE-PolyBench / Keras | 将保存逻辑统一到保存 API；选定保存测试 | PASS |
| SWE-bench Pro / Open Library | 迁移公共转换函数，随后修复署名和页数字段丢失 | PASS |
| ScarfBench / PetClinic | 本地改编的查找逻辑抽取；Spring、JPA、H2 | PASS |

Open Library 最初是 **FAIL**：两个上游 xfail 用例在强制执行后仍有断言失败。补齐业务逻辑后，原阈值和官方断言保持不变，使用 `--runxfail --reruns 0` 执行得到 PASS。原回归有 13 项，验收有 41 项，两组包含重复测试。这个结果包括函数迁移之后的缺陷修复，最初的 FAIL 记录仍保留。

开发工作区中的独立 benchmark 运行器也通过了 21 项回归测试。它与实验材料一起留在本地，安装 Skill 无需使用它。

## 改造样例：从控制器中抽出域名删除调度

来源为 SWE Atlas / SimpleLogin，任务 `task-69391d8d1ce51c407be1e533`，项目原始提交为 `7bdafc5974898fe05b5d80d0999218aa47ca58f8`。

用户请求删除域名时，系统会把域名标为待删除，并创建包含域名 ID 的后台任务，页面随后提示“已安排删除”。这次改造把这个操作集中到 `app/custom_domain_utils.py` 的 `delete_custom_domain`，保留任务参数和原有提交行为。

下面的流程伪代码根据实际补丁重新编写，省略了日志、权限检查和其他分支。`create_deletion_job` 代表实际的 `Job.create(...)`，`deletion_notice` 代表页面提示与响应。

### 改造前

页面控制器负责状态修改、任务创建和页面响应：

```python
def domain_detail(domain):
    domain.pending_deletion = True
    create_deletion_job(domain.id, run_at=now(), commit=True)
    return deletion_notice(domain)
```

### 改造后

状态修改和任务创建一起迁入新函数，控制器调用这个操作：

```python
def delete_custom_domain(domain):
    # 保留待删除标记与后台任务共同提交的原有行为。
    domain.pending_deletion = True
    create_deletion_job(domain.id, run_at=now(), commit=True)


def domain_detail(domain):
    delete_custom_domain(domain)
    return deletion_notice(domain)
```

“安排删除”是一个完整的业务操作，这也是抽取边界的依据。`CustomDomain` 和 `Job` 继续表达现有状态与持久化行为；控制器专注页面流程，体现了 SRP 的职责分离。一个函数已经足够承接这次变化。

新函数仍依赖项目现有 ORM 和任务模型。注释提醒维护者保留共同提交的行为，测试则检查具体状态和调用结果。

### 验收结果

| 检查 | 改造前 | 改造后 |
|---|---|---|
| 原有领域工具回归 | PASS，14 项 | PASS，同一组 14 项 |
| 独立删除操作 | 原始源码中尚未实现 | PASS，存在 `delete_custom_domain` |
| 控制器委托 | 直接创建任务 | PASS，调用新操作，不再直接创建 `Job` |
| 删除行为专项测试 | 基线阶段未执行 | PASS，覆盖待删除标记、任务内容、返回值及已待删除输入 |
| 修改范围与测试保护 | 已固定基线和保护文件 | PASS，修改在约定范围内，上游测试未变 |

验收共执行 18 项测试，其中包含原有 14 项回归，环境使用 PostgreSQL 和 Redis。最终结果为 **PASS**。基线阶段没有运行的新增测试记为未执行。

开发记录保存在 `benchmarks/large/patches/atlas.patch`、`benchmarks/large/results/atlas-baseline-final/` 和 `benchmarks/large/results/atlas-after/`，这些路径位于未分发的本地实验目录。

## 怎样理解这些结果

这些记录验证了所选任务的实现和验收流程。Atlas 运行了可执行测试，未运行其 LLM rubric；PetClinic 使用本地改编任务，未执行 ScarfBench 官方框架迁移。四项试跑也没有设置有/无 Skill 的受控对照，因此不能用它们推断 Skill 带来的因果提升。

静态架构分析针对 Python，运行时和共享数据关系由配置显式声明。领域边界、对象职责和模式成本需要业务评审；自动 PASS 表示已声明的可执行条件得到满足。
