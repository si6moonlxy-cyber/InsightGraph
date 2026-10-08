# InsightGraph 系统架构

> 最后更新：2026-10-03
>
> 当前阶段：Phase 2A——后端骨架、领域契约、本地 Collector 与 Python Analyzer（含首个 Golden Dataset）已建立；持久化与 GraphRAG 尚未实现。
>
> 本文档是系统架构真源；哲学与设计理由见[Introduction to Initialization Architecture Concepts](Introduction%20to%20Initialization%20Architecture%20Concepts.md)，
> 分步执行与当前进度见 [Development Plan](Development%20Plan.md)。

## 1. 项目目标与边界

InsightGraph 用两张语义不同、可以互相引用的图帮助人理解软件项目：

- **CodeGraph** 回答“代码如何组织和调用”。
- **GraphRAG** 回答“项目为什么被认为具备某项能力，这个判断由什么证据支撑”。

MVP 首先分析本地 Python 仓库，产出可重复验证的 CodeGraph。多语言、云端协作、复杂权限、
自动部署和无证据的开放式结论不属于当前阶段。

## 2. 当前真实状态

| 能力 | 状态 | 当前事实 |
| --- | --- | --- |
| 工程基础设施 | 已建立 | CI、Git Hooks、Docker Compose、文档治理和评测规则存在 |
| 后端骨架 | 已建立 | FastAPI、Settings、统一错误、健康检查、领域/应用/基础设施分层 |
| 领域契约 | 稳定契约已建立 | CodeGraph 稳定 ID、ScanResult 与阶段错误契约、确定性序列化与 schema_version（ADR-010/011）；真实适配器未实现 |
| CodeGraph Collector | 已实现 | `GitRepositoryCollector`：git 枚举（ignore 单一真源）、LF 归一哈希与局部错误通道（步骤 3） |
| Python Analyzer | 已实现 | `PythonAstAnalyzer`：Module/Class/Function + DEFINES/IMPORTS（步骤 4）；eval/codegraph 首个 Golden Dataset（语义 100%） |
| 持久化适配器 | 未实现 | 当前只有 Repository Protocol，没有数据库或 JSON 实现 |
| GraphRAG 引擎 | 未实现 | 只有严格隔离的最小领域契约 |
| LangGraph 工作流 | 未实现 | `workflows/` 只声明边界，尚未引入依赖 |
| 前端 | 未建立 | Phase 3 再建立 Vite + React 应用 |
| 基础设施运行状态 | 部分已启动 | postgres 与 redis 容器本机运行且 healthy（2026-10-02 验证，宿主端口可达）；neo4j 未启动；宿主 5432/6379 与 love-lobster 冲突——跑本栈前先停其容器 |

## 3. 系统上下文

```text
用户
 │  提交本地仓库 / 查询图谱 / 查看证据
 ▼
InsightGraph API
 ├── 读取待分析代码仓库
 ├── 生成 CodeGraph 与证据
 ├── 组织 GraphRAG Claim
 └── 查询 PostgreSQL / Neo4j / Redis / Artifact Store

LLM Provider（可选）
 └── 只参与需要语义判断的 GraphRAG 与报告任务
     未配置 LLM 时，确定性 CodeGraph 仍可运行
```

## 4. 后端分层与依赖方向

```text
backend/app/
├─ api/                         # HTTP 协议、请求校验、响应转换
├─ application/                 # 用户用例：扫描、查询、报告
│  └─ scans/
├─ domain/                      # 纯领域规则与稳定契约
│  ├─ codegraph/
│  ├─ evidence/
│  └─ graphrag/
├─ infrastructure/              # 外部技术适配器
│  ├─ collectors/
│  ├─ analyzers/
│  ├─ persistence/
│  └─ llm/
├─ workflows/                   # LangGraph 编排入口
├─ foundation/                  # 配置、日志、错误、生命周期
└─ main.py
```

唯一允许的主要依赖方向：

```text
api ─────────────┐
workflows ───────┼──> application ───> domain
                 │                       ▲
infrastructure ──┴───────────────────────┘
                     实现内层定义的端口
```

硬性规则：

1. `domain/` 不导入 FastAPI、SQLAlchemy、Neo4j、Redis、LangGraph 或 LLM SDK。
2. `api/` 不直接访问数据库，不承载分析规则。
3. `application/` 编排领域对象和端口，不感知具体存储技术。
4. `infrastructure/` 实现端口，不反向定义领域规则。
5. `workflows/` 只组合应用用例，不承载核心分析算法。
6. 跨层传递使用明确的 Pydantic 契约，禁止散装 `dict`。

这些规则由 `tests/architecture/` 自动检查，而不只依赖人工约定。

## 5. CodeGraph 与 GraphRAG 边界

### 5.1 CodeGraph

CodeGraph 是程序分析图：

```text
Module / Class / Function
DEFINES / IMPORTS / CALLS
```

Repository 是图的作用域（由图的 `repository_id` + `revision` 界定），不是节点类型。图的根
携带 `schema_version`、`repository_id`、`revision` 与 `parser_version`；节点携带稳定 ID、语言、
文件路径、源码行号与内容哈希。稳定 ID、路径与哈希口径、确定性序列化纪律见
[ADR-010](adr/ADR-010-codegraph-contract-discipline.md)；扫描结果与错误契约见
[ADR-011](adr/ADR-011-scan-result-contract.md)。相同仓库、Commit 与配置应产生相同结果。

当前 schema v2 已实现 CALLS：边携带调用点 `source_span`、`resolved/ambiguous` 解析状态与
歧义截断标记；dynamic/unresolved 不建边而进入扫描漏斗。代码入口以图级 `entries` 清单表达，
不混入 EdgeKind。scanner-only 产物的 `provenance` 为空；启用 M2 外部引擎且整批查询成功时记录 Provider 版本、资产哈希与工具名。

### 5.2 GraphRAG

GraphRAG 是研究证据图：

```text
Technology / Concept / Capability
Claim
DocumentEvidence / CodeEvidence
```

`SUPPORTED` Claim 必须至少引用一条 Evidence；无直接证据时必须标记为 `INFERENCE`、
`HYPOTHESIS` 或 `UNSUPPORTED`。

### 5.3 连接方式

GraphRAG 可以通过 `codegraph_node_id` 引用 CodeGraph 节点，但不能把 Function、Class、Module
直接转换成 Technology、Concept 或 Capability。两类图分别维护 Schema、Repository 和评测指标。

## 6. 第一条纵向链路

```text
ScanRequest
  → RepositoryCollector
  → SourceManifest
  → PythonAnalyzer
  → CodeGraph IR
  → Validator
  → JSON Artifact / CodeGraphRepository
  → Query API
```

当前本地 Python 链路已实现 Module、Class、Function、IMPORTS、DEFINES、CALLS 与入口清单；
CALLS 采用确定性浅绑定并保守区分 resolved、ambiguous、dynamic、unresolved。CodeGraphAI 通过
`infrastructure/code_intelligence` 的 Provider → Raw DTO → Canonical Adapter 可选接入；外部引擎无
call-site 证据的 engine-only 边不物化，任何探测/查询失败或超过默认 900 秒整批预算均降级为 scanner-only。
因此大型仓库的正确性不依赖外部引擎能否在预算内完成；多语言与远程 GitHub 仓库仍在后续迭代。

完成标准：

- 单文件失败不终止整个仓库扫描。
- 所有节点都能回溯到文件和准确行号。
- 相同输入生成稳定排序、稳定 ID 和相同 Artifact。
- 首个 Golden Dataset 上的基础节点与关系达到 100% 正确。

## 7. 数据与存储职责

| 存储 | 目标职责 | 当前状态 |
| --- | --- | --- |
| PostgreSQL 16 | Repository、Scan、Job、配置、报告元数据 | Compose 就绪，适配器未实现 |
| pgvector | 文档和代码证据的语义检索 | 扩展初始化脚本就绪，未使用 |
| Neo4j | GraphRAG 知识、Claim 与 Evidence 关系 | Compose 就绪，适配器未实现 |
| Redis | Job 状态、LangGraph checkpoint、短期缓存 | Compose 就绪，适配器未实现 |
| JSON Artifact | 第一阶段 CodeGraph 输出、快照和评测基线 | 待实现 |

CodeGraph 最终物理存储暂不锁定。先通过 JSON Artifact 和 Repository 端口获得真实规模与查询证据，
再决定是否进入 PostgreSQL、Neo4j 或专门存储，见 ADR-002 与 ADR-006。

## 8. 运行与部署

当前可运行部分：

```text
FastAPI :4000
├── GET /api/v1/health/live
└── GET /api/v1/health/ready

Docker Compose
├── PostgreSQL + pgvector :5432
├── Neo4j HTTP/Bolt       :7474/:7687
└── Redis                 :6379
```

API 尚未加入 Compose。骨架阶段 `/ready` 不访问外部依赖；启用持久化适配器后，`/ready` 才加入对应
健康检查。应用导入和单元测试不得隐式连接任何外部服务。

## 9. 配置、错误与可观测性

- 配置统一由 `foundation/config.py` 的 Pydantic Settings 读取。
- 只有实际启用的适配器才要求对应配置，避免 CodeGraph 被 LLM 或数据库配置阻断。
- 应用错误统一映射为结构化响应，Router 不重复捕获业务异常。
- 日志统一使用标准 `logging`，禁止输出密钥和完整敏感源码。
- 后续扫描任务必须带 `scan_id`、`repository_id`、`revision` 和阶段信息，支持复现与追踪。

## 10. 测试与评测

测试分为三层：

1. `tests/unit/`：领域不变量、应用用例和 API 契约；不连接外部服务。
2. `tests/architecture/`：依赖方向和禁止导入规则。
3. `tests/integration/`：显式标记 `integration`，只在指定命令下运行。

CodeGraph、GraphRAG、检索和报告属于核心能力，遵守：

```text
Baseline First → Change → Same Eval → Delta
```

第一项 Python Analyzer 必须同步建立 Golden Repository、固定期望结果和 evaluator。

## 11. 演进顺序

1. **Phase 2A（当前）**：后端骨架、领域契约、依赖守卫、文档与 ADR。
2. **Phase 2B**：本地 Collector、Python AST Analyzer、确定性 JSON Artifact、Golden Dataset。
3. **Phase 2C**：扫描 API、PostgreSQL 元数据、后台 Job 与 Redis 状态。
4. **Phase 2D（进行中）**：CALLS scanner 与 CodeGraphAI Provider/Canonical Adapter 已完成；继续 ADR-012 落账、增量扫描和 CodeGraph 查询。
5. **Phase 2E**：GraphRAG Evidence/Claim、Neo4j、pgvector 与统一 LLM Gateway。
6. **Phase 2F**：LangGraph 编排和 Evidence First Reporter。
7. **Phase 3**：React 图谱浏览器、视觉回归和真实 LLM 手动评测工作流。

## 12. 架构决策

| ADR | 决策 | 状态 |
| --- | --- | --- |
| [ADR-001](adr/ADR-001-codegraph-graphrag-boundary.md) | CodeGraph 与 GraphRAG 职责边界 | Accepted |
| [ADR-002](adr/ADR-002-storage-responsibilities.md) | 存储职责分工 | Proposed |
| [ADR-003](adr/ADR-003-langgraph-orchestration-only.md) | LangGraph 只作为编排层 | Accepted |
| [ADR-004](adr/ADR-004-evidence-first-claims.md) | Evidence First 结论约束 | Accepted |
| [ADR-005](adr/ADR-005-local-python-mvp.md) | MVP 先支持本地 Python 仓库 | Accepted |
| [ADR-006](adr/ADR-006-codegraph-json-artifact-first.md) | CodeGraph 首先使用 JSON Artifact | Proposed |
| [ADR-007](adr/ADR-007-datamodel-sqlalchemy-first.md) | 数据模型视图第一版从 SQLAlchemy 模型静态提取 | Proposed |
| [ADR-008](adr/ADR-008-datamodel-independent-third-layer.md) | 数据模型视图作为独立第三语义层 | Proposed |
| [ADR-009](adr/ADR-009-database-schema-normalization.md) | 数据库 Schema 推导与范式纪律 | Proposed |
| [ADR-010](adr/ADR-010-codegraph-contract-discipline.md) | CodeGraph 契约纪律：稳定 ID、路径与哈希口径、确定性序列化 | Proposed |
| [ADR-011](adr/ADR-011-scan-result-contract.md) | 扫描结果契约：单一 ScanResult、阶段 Outcome 与错误模型 | Proposed |
