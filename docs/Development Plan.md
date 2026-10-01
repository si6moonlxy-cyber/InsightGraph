# InsightGraph Development Plan

> 最后更新：2026-10-01
>
> 当前阶段：Phase 2A，建设步骤 0、1 已完成，步骤 2 已建立初版契约；下一步完成步骤 2 的剩余契约，
> 然后进入步骤 3“本地仓库采集器”。
>
> 架构真源见[系统架构](architecture.md)，设计哲学见
> [初始化架构思想导论](Introduction%20to%20Initialization%20Architecture%20Concepts.md)。

## 1. 计划目的

InsightGraph 按“先确定性地理解代码，再用证据组织知识，最后建设交互产品”的顺序开发：

```text
0 校准真源
→ 1 后端工程骨架
→ 2 领域模型
→ 3 本地采集器
→ 4 Python 分析器
→ 5 调用关系
→ 6 持久化
→ 7 数据模型视图
→ 8 API 与任务
→ 9 GraphRAG
→ 10 编排与产品层
```

每一步都必须形成可运行、可测试、可复现的增量。目标架构已经写入文档但尚未实现的部分，统一标记为
“未开始”或“进行中”，不得当成现有能力。

## 2. 状态说明

| 状态 | 含义 |
| --- | --- |
| ✅ 已完成 | 交付物已存在，完成门槛已经验证 |
| 🟡 进行中 | 已有可用产物，但尚未满足本步骤全部完成门槛 |
| ⏭ 下一步 | 当前完成在手工作后立即建设 |
| ⬜ 未开始 | 仅有设计或 ADR，尚无可运行实现 |

## 3. 当前进度总览

| 步骤 | 建设内容 | 状态 | 当前事实 |
| --- | --- | --- | --- |
| 0 | 校准真源 | ✅ 已完成 | 架构真源、思想导论、ADR 体系与文档索引已经建立 |
| 1 | 后端工程骨架 | ✅ 已完成 | FastAPI、Settings、日志、错误、分层目录、依赖锁和质量门禁已通过 |
| 2 | 领域模型 | 🟡 进行中 | CodeGraph、Evidence、GraphRAG Claim、扫描端口已有初版；稳定 ID 与完整扫描结果契约待补 |
| 3 | 本地采集器 | ⏭ 下一步 | 只有 `RepositoryCollector` Protocol，尚不能读取真实仓库 |
| 4 | Python 分析器 | ⬜ 未开始 | 只有 `CodeAnalyzer` Protocol，尚无 AST 实现和 Golden Dataset |
| 5 | 调用关系 | ⬜ 未开始 | `CALLS` 仅存在于 EdgeKind，尚无符号解析实现 |
| 6 | 持久化 | ⬜ 未开始 | 只有 `CodeGraphRepository` Protocol，尚无 JSON/数据库适配器 |
| 7 | 数据模型视图（datamodel） | ⬜ 未开始 | ADR-007/008/009 已定；复用步骤 3/4 解析设施与步骤 6 Artifact 纪律 |
| 8 | API 与任务 | ⬜ 未开始 | 当前只有健康检查，没有扫描、进度或查询 API |
| 9 | GraphRAG | ⬜ 未开始 | 只有知识节点与 Claim 不变量，没有证据抽取、检索或图构建 |
| 10 | 编排与产品层 | ⬜ 未开始 | LangGraph、Reporter 和 React 图谱浏览器均未实现 |

## 4. 分步建设计划

### 0. 校准真源

**目标**

在编码前统一项目目标、当前现实、架构边界和决策记录，避免依据理想态文档产生旁路实现。

**交付物**

- `docs/architecture.md`：系统架构真源。
- 初始化架构思想导论：架构哲学。
- `docs/adr/ADR-001` 至 `ADR-006`：首批架构决策。
- `CLAUDE.md`：开发红线与同步规则。

**完成门槛**

- CodeGraph 与 GraphRAG 边界明确。
- 当前状态与目标状态分开描述。
- 所有文档链接通过自动检查。

**状态：✅ 已完成。**

### 1. 后端工程骨架

**目标**

建立可以启动、测试并持续演进的后端底座，先固定依赖方向，不提前引入业务复杂度。

**交付物**

- FastAPI 应用工厂与 `/api/v1/health/live`、`/ready`。
- Pydantic Settings、CORS、统一错误与日志。
- `api → application → domain ← infrastructure` 分层。
- Python 3.12、uv lock、Ruff、Mypy、pytest 和架构测试。

**完成门槛**

- 应用导入和单元测试不连接外部服务。
- 领域层禁止导入 FastAPI、SQLAlchemy、Neo4j、Redis、LangGraph。
- 本地全量质量门禁通过。

**状态：✅ 已完成。**

### 2. 领域模型

**目标**

定义独立于数据库、API 和编排框架的稳定语言，使 Collector、Analyzer、Repository 与 GraphRAG
能够通过清晰契约协作。

**已完成**

- `CodeNode`、`CodeEdge`、`CodeGraph`、`SourceSpan`。
- `Evidence`、`EvidenceStatus`、`SourceReference`。
- `KnowledgeNode` 与强制 Evidence 的 `Claim`。
- `ScanRequest`、`SourceManifest`、Collector/Analyzer/Repository Protocol。

**剩余工作**

- 定义稳定 ID 生成规则并实现纯函数构造器。
- 增加 `ScanResult`、阶段错误、单文件失败和统计契约。
- 明确路径规范化、语言标识、哈希算法和 Schema 版本。
- 增加序列化稳定性与 Schema 兼容测试。

**完成门槛**

- 相同输入生成相同 ID 与相同序列化结果。
- 所有阶段都能用结构化类型表达成功、局部失败和整体失败。
- 领域契约无需启动 FastAPI 或数据库即可完整测试。

**状态：🟡 进行中。**

### 3. 本地采集器

**目标**

把一个本地 Git 仓库转换成确定性 `SourceManifest`，只收集事实，不分析代码语义。

**应实现**

- 校验仓库路径和访问边界，拒绝越界与危险软链接。
- 读取 Git revision、仓库根目录和工作区状态。
- 尊重 `.gitignore` 与项目排除规则。
- 只采集目标语言文件，计算内容哈希并稳定排序。
- 记录无法读取、编码异常、文件消失等局部错误。

**完成门槛**

- 同一 revision 重复采集得到相同 Manifest。
- 单文件错误不会中断整个仓库。
- 不进入 `.git`、虚拟环境、构建产物或密钥文件。
- Windows 路径、Unicode 文件名和软链接有自动测试。

**状态：⏭ 下一步。**

### 4. Python 分析器

**目标**

使用 Python 标准库 AST 把 `SourceManifest` 转换为基础 CodeGraph。

**应实现**

- Module、Class、Function 节点。
- DEFINES、IMPORTS 关系。
- qualified name、装饰器、异步函数、嵌套定义和准确行号。
- 语法错误隔离与解析统计。
- 小型 Golden Repository、固定期望 JSON 与 evaluator。

**完成门槛**

- 基础节点与关系在首个 Golden Dataset 上达到 100%。
- 相同输入输出字节级稳定的规范化 Artifact。
- 每个节点可回溯到真实文件与源码行范围。

**状态：⬜ 未开始。**

### 5. 调用关系

**目标**

在基础结构图稳定后增加 CALLS、入口识别和跨模块符号解析。

**应实现**

- 本地函数、方法、导入别名和模块属性调用解析。
- 明确区分 resolved、ambiguous、dynamic、unresolved。
- CLI、FastAPI、脚本等入口节点识别。
- 调用关系独立 Golden Cases 与误报/漏报指标。

**完成门槛**

- 不把动态推测伪装成确定调用关系。
- 解析精度、召回率和未解析比例可重复测量。
- 基础 Module/Class/Function/IMPORTS/DEFINES 不发生回归。

**状态：⬜ 未开始。**

### 6. 持久化

**目标**

先让 CodeGraph 可保存、可比较、可重载，再依据真实规模决定最终数据库。

**应实现**

- 规范化 JSON Artifact Repository。
- Artifact Schema 版本、原子写入和内容哈希。
- PostgreSQL 中的 Repository、Scan、Job 元数据与 Alembic。
- Schema 按 ADR-009 执行：访问模式先行（每张表先写必须回答的查询），默认 3NF + 例外登记。
- 表/列注释描述“为什么存在”，并产出 `docs/architecture/数据模型.md`（表 → 契约/用例映射与耦合清单）。
- 基于真实查询样本评审 CodeGraph 最终物理存储。

**完成门槛**

- 保存再读取不改变领域对象。
- Baseline 不会被默认覆盖。
- 中断写入不会留下被误认为完整的 Artifact。
- 每张表、每个索引都能指向具体查询或业务不变量；每个范式例外都有登记理由。
- 用测量结果决定是否接受或替代 ADR-002、ADR-006。

**状态：⬜ 未开始。**

### 7. 数据模型视图（datamodel）

**目标**

在 CodeGraph 解析设施（步骤 3/4）与 Artifact 纪律（步骤 6）就绪后，静态解析目标仓库的
SQLAlchemy 模型，产出第二类确定性分析产出：数据模型视图（视图页 UI 归属产品层）。与 CodeGraph
单向引用，与 GraphRAG 解耦。

**应实现**

- 复用 Collector 与 Python AST 设施解析 SQLAlchemy 模型（Declarative Base 子类及关系声明）。
- datamodel IR：表、列、物理约束（外键 / 主键 / 唯一 / 非空）与 ORM 声明关系（relationship /
  backref / 关联表）；命名约定推断不入第一版。
- 每个节点与每条边带源码行号证据；确定性 Artifact 与独立 Golden Dataset / 评测口径。
- 与 CodeGraph 单向引用（表 → 定义它的 Class），跨层 join 只发生在查询与展示层。
- “使用耦合”（哪些类 / 函数读写哪张表）为第二版第一优先，另行评审。

**完成门槛**

- 相同输入产生字节级稳定的 datamodel Artifact。
- 首个 Golden Dataset 上表 / 列 / 约束 / 关系达到 100%。
- 不连接目标数据库；不含命名约定推断。
- CodeGraph 基础评测不发生回归。

**状态：⬜ 未开始。**

关联决策：ADR-007（输入边界）、ADR-008（语义边界）。

### 8. API 与任务

**目标**

把同步分析闭环暴露为稳定 API，再增加后台任务和进度状态。

**应实现**

- 创建扫描、查询扫描状态、读取图节点和邻居。
- 查询节点对应源码证据。
- Job 状态机、幂等键、取消、失败重试与 Redis 状态。
- PostgreSQL/Redis/Artifact 的就绪探针。

**完成门槛**

- API Router 不直接访问数据库或 Analyzer。
- 同一幂等请求不会重复创建扫描。
- 重启后可恢复或明确终止进行中的任务。
- 错误响应和阶段状态有稳定 Schema。

**状态：⬜ 未开始。**

### 9. GraphRAG

**目标**

在 CodeGraph 可信后，构建 Technology、Concept、Capability、Claim 与 Evidence 组成的研究证据图。

**应实现**

- 文档与代码 Evidence 抽取。
- Claim 可信状态和 CodeGraph 引用。
- Neo4j GraphRAG Repository 与 pgvector 检索。
- 统一 LLM Gateway、Provider Registry、超时、熔断和审计。
- Evidence Recall、Hit@K、MRR 与 Evidence Coverage 评测。

**完成门槛**

- `supported` Claim 必须能回到真实证据。
- CodeGraph 节点不会被直接等同为 GraphRAG 知识实体。
- 没有 LLM 配置时，CodeGraph 仍能独立运行。
- 同 Dataset、Gold、Metric 输出 Before/After/Delta。

**状态：⬜ 未开始。**

### 10. 编排与产品层

**目标**

在各阶段可独立测试后，用 LangGraph 编排完整分析流程，并建设可探索的用户界面和证据报告。

**应实现**

- Collector → Analyzer → GraphBuilder → Reviewer → Reporter 工作流。
- checkpoint、暂停恢复、重试和人工审核节点。
- Evidence First Reporter 与可导出报告。
- Vite + React 图谱浏览器、节点详情、证据回溯和扫描进度。
- 视觉回归与真实 LLM 手动评测工作流。

**完成门槛**

- LangGraph 节点只调用应用用例，不包含核心算法。
- 用户能从任一关键结论回溯到证据与源码。
- 前端不复制后端业务规则。
- 关键产品路径有 E2E 和视觉基线。

**状态：⬜ 未开始。**

## 5. 现在应该做什么

当前不要直接接 Neo4j、LangGraph、LLM 或前端。下一阶段按下面顺序推进：

### 当前任务 A：完成步骤 2

1. 实现 CodeGraph 稳定 ID 构造器。
2. 增加 `ScanResult`、`ScanError`、统计与 Schema 版本。
3. 增加稳定序列化和错误契约测试。
4. 复核领域层依赖守卫。

### 紧接任务 B：实现步骤 3

1. 实现本地 Git 仓库 Collector。
2. 生成确定性 `SourceManifest`。
3. 覆盖 ignore、Unicode、软链接和局部失败测试。
4. 暂时不解析 AST。

### 第一个产品能力里程碑：完成步骤 4

Collector 稳定后，建立 Python AST Analyzer 和首个 Golden Repository，形成：

```text
本地 Python 仓库
→ SourceManifest
→ CodeGraph IR
→ 确定性 JSON
→ Golden Dataset 验证
```

只有这条闭环通过，才进入 CALLS、数据库和异步任务。

## 6. 更新纪律

每完成一个步骤，必须同步更新：

- 本文档的进度总览、步骤状态和下一步。
- `docs/architecture.md` 的当前真实状态。
- `CLAUDE.md` 的模块速查和状态地图。
- 对应测试、评测与 ADR 状态。

“代码已合并”不自动等于“步骤已完成”；只有该步骤的完成门槛全部通过，状态才能从进行中改为已完成。
