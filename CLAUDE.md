# CLAUDE.md — InsightGraph 行为守则

> Solo dev 项目，Agent 辅助开发。
> **核心法则：Evidence First（证据优先）。文档过时 = 生产 Bug，优先级等同。**
>
> 当前阶段：Phase 2A —— 工程基础设施、`backend/` 架构骨架、领域契约（ADR-010/011）、本地 Collector 与
> Python Analyzer（步骤 3/4，含首个 Golden Dataset）已就位，持久化适配器、GraphRAG 引擎与 `frontend/` 尚未建立
> （见 §五 5.3 当前代码-文档现实）。

---

## 一、动手前（Pre-Flight，强制）

### 1.1 先读再写（最高优先级）

**每次任务开始前，第一件事就是读本文件（CLAUDE.md）。** 这是所有行为的入口，不可跳过。

读完 CLAUDE.md 后，按需读取：

1. [docs/README.md](docs/README.md) — 当前文档体系总览
2. 变更所涉模块的对应文档（CodeGraph 改 → 读 CodeGraph 设计；DB 改 → 读数据模型）
3. 确认文档**还存在**且**与代码一致**。否则先修文档，再改代码

### 1.2 死链零容忍

发现 CLAUDE.md / docs/ 中有文件路径不存在的引用——立即修正或删除。**不允许“先放着以后修”。**

### 1.3 变更范围声明

动笔前，用一句话声明本次变更波及哪些文件（代码 + 文档）。这个声明就是 checklist。

### 1.4 动态文档维护（每次任务必做）

文档维护是编码流程的**内置环节**，不是独立任务。每次任务中自动触发：

- **代码变更时**：对照 §四 文档同步矩阵，更新对应文档
- **顺手发现腐败时**：死链 / 幽灵模块 / 过时路径 / 重复描述 / 过期日期（>90 天）→ 立即修复，不作为独立任务
- **重大变更完成时**：更新对应架构文档与评测记录
- **任务登记（AI 代笔，口述即写入）**：用户口述任务的开始 / 完成 / 变化 → AI 直接维护 `.devlog/DEV_LOG.md` 并自动提交推送；格式、区块、颗粒度由 AI 决定，用户只做轻量 review（命令细节见 §5.2）

**原则：发现腐败不修 = 新增 Bug。文档过时和生产 Bug 优先级等同。**

### 1.5 核心变更评测门禁（最高优先级）

涉及 CodeGraph / GraphRAG / Reporter / 检索 / 排序 / Prompt / Embedding / 评分阈值、或会明显改变分析结果的交互时，开始修改前必须遵守：

- **Baseline First**：修改前使用固定数据集（Dataset / Gold / Metric）运行并保存可复现基线；没有基线，不得以“效果优化”为目标直接改实现
- **Same Eval**：修改后必须使用同一 Dataset、Gold、Metric 与 Guardrail 重跑
- **Delta Required**：汇报必须包含 Before / After / Delta / Regression，不能只给修改后的单点结果
- **明确口径**：缺少修改后评测时，只能标记“实现完成，评测未完成”，不得声称“优化完成”
- 详细规则见 [工程基础设施文档 §8](docs/InsightGraph_Engineering%20Infrastructure.md) 与 `eval/README.md`

### 1.6 架构疑问先查文档

架构 / 技术栈类问题，先查 [docs/architecture.md](docs/architecture.md)（系统架构真源：当前状态、边界、依赖方向与演进路线）与
[docs/初始化架构思想导论.md](docs/Introduction%20to%20Initialization%20Architecture%20Concepts.md)（设计哲学：为什么这样分）；工程细则见
[docs/InsightGraph_Engineering Infrastructure.md](docs/InsightGraph_Engineering%20Infrastructure.md)。
查不到细颗粒度信息，再搜索整个仓库。目的：节省时间、保持宏观视角。

---

## 二、架构硬约束：CodeGraph 与 GraphRAG 边界

CodeGraph 负责回答：

> “代码是如何组织和调用的？”

```text
Function / Class / Module
IMPORTS / CALLS / DEFINES
代码入口 / 模块依赖
```

GraphRAG 负责回答：

> “这个项目为什么被认为具备某种技术能力，
> 这个判断由哪些文档证据和代码证据支持？”

```text
Technology / Concept / Capability
ProjectClaim
DocumentEvidence / CodeEvidence
Evidence Relationship
```

红线（违反 = review 打回）：

```text
1. CodeGraph 与 GraphRAG 必须严格区分，禁止合并成一个没有语义边界的万能图。
2. 禁止把 CodeGraph 节点（Function / Class / Module）直接等同于 GraphRAG 知识节点。
3. 所有“项目具备某能力”的结论必须附 Evidence（文件路径 + 行号或文档出处）。
4. 没有直接证据时必须显式标记：inference / hypothesis / unsupported。
5. Router 不写业务逻辑。
6. Collector、CodeAnalyzer、GraphBuilder、Reviewer、Reporter
   必须通过明确的数据结构传递结果。
7. 禁止 Agent 绕过统一 Repository / Evidence Store。
8. 新增分析能力必须同步补充：
   test / evidence schema / evaluation case / documentation。
9. GraphRAG 可以引用 CodeGraph 节点；CodeGraph 不承担项目技术事实推理。
```

以及本仓库的最高文档原则：

```text
架构文档描述的是当前真实系统，而不是理想设计。

如果：
文档 != 代码

则：
以代码真实状态为准，并更新文档。
```

以及 POC 代码隔离（铁律）：

```text
1. POC 代码必须隔离在 poc/ 目录下（或独立分支），严禁合并入 dev / main 主分支。
2. POC 完成后，必须以正式架构纪律重写，方可进入生产代码。
3. POC 的唯一目标是验证技术可行性，不求代码质量。
```

强制层（由 `scripts/poc-guard.sh` 统一实现，三处执行）：main / dev 出现被跟踪的 `poc/`、
生产代码（`backend/app`、`frontend/src`）引用 `poc`、`poc/` 缺少非空 `README.md`
（spike 目标 / 验证结论 / 重写去向）→ 一律拒绝。
执行点：`.githooks/pre-commit`、`scripts/ci-check.sh`、`.github/workflows/ci.yml`。

---

## 三、编码规范

### 3.1 硬性规范（违反 = review 打回）

| 规则 | 说明 |
|------|------|
| 结构化输出必须用 Pydantic | 不允许手写 JSON + regex 修复 |
| 所有 LLM 调用走统一网关 | 统一入口 `backend/app/llm/`，不允许各模块直接 import httpx 调外部 API |
| Provider 路由必须用 registry | 新 provider 只改注册 + 配置，不动路由代码 |
| 严禁循环 import | 发现 cycle → 抽公共层重构，不要加 `TYPE_CHECKING` 绕过 |
| 禁止跨模块 import 私有符号 | 下划线前缀（`_xxx`）是"内部实现"约定，公共逻辑必须提取到独立模块 |
| 禁止版本号文件模式 | 新增文件不准用 `XxxV2` / `V3` 这类命名 |
| 注释必须用中文 | 代码注释一律用中文；改到旧文件时顺手将英文注释转为中文 |
| 密钥只能从环境变量读取 | 禁止硬编码 API Key / 密码 / 令牌（见 §六 安全扫描） |
| 日志用 `logging.getLogger(__name__)` | 禁止 `print()`；禁止在日志中打印密钥 |
| 数据库访问走统一数据层 | SQLAlchemy ORM / 统一 Repository，禁止在 Router 中散写 SQL |
| Evidence 不许伪造 | 没有直接证据的结论必须标记 inference / hypothesis / unsupported，见 §二 |

### 3.2 弹性规范（新代码遵守、存量逐步消化，不 blocker）

模块大小：

| 规则 | 宽松阈值 | 硬上限（必须拆） |
|------|---------|----------------|
| Router handler | ≤ 80 行 | > 150 行 |
| Service 文件 | ≤ 800 行 | > 1000 行 |
| 前端组件 | ≤ 400 行（新代码） | > 600 行（任何代码） |
| 自定义 hooks | 第二次复用时才抽 | 第三次复用还不抽就算违规 |

测试策略：

| 场景 | 怎么做 |
|------|--------|
| Bug fix | **必须**先写测试复现，再修 |
| 关键链路（CodeGraph 解析 / Evidence 生成 / 报告结论） | **建议** TDD，至少关键路径有覆盖 |
| 新功能 / 重构 | 稳定后补测试，不 blocker 开发 |
| 探索 / 原型 | 先跑起来，不要求测试 |
| 简单 CRUD | 可以不写单测，但要手动验证 |

暂停修改后运行 `bash scripts/ci-check.sh`（本地全量检查）确认不破坏现有功能。

---

## 四、完成后（Post-Task 文档同步，强制）

### 4.1 文档同步矩阵

| 代码变更 | 必须更新 |
|----------|----------|
| 新增 / 修改数据模型或字段 | `docs/architecture.md` 数据模型章节（后端建立后拆分为独立文档） |
| CodeGraph 解析 / IR 变更 | CodeGraph 设计文档（待 backend 建立后创建于 `docs/architecture/`） |
| GraphRAG / Evidence Schema 变更 | GraphRAG 设计文档 + Evidence Schema 定义 |
| 新增 / 修改 Prompt | Prompt 架构文档（待创建于 `docs/architecture/`） |
| 架构变动（模块 / 依赖 / 分层） | [docs/architecture.md](docs/architecture.md) |
| 评测流程、Dataset / Gold、Baseline 或指标门禁变更 | `eval/README.md` + 对应 evaluator 的 cases / baselines |
| 环境变量变更 | `.env.example` +（后端建立后）`docs/operations/环境变量清单.md` |
| 新增 / 重命名模块 | 本文件 §五 5.4 模块速查表 |
| 重大变更完成 | 对应文档 + 评测记录（Before / After / Delta） |

### 4.2 文档质量底线

- **不写“待补充”。** 要么写完整，要么删掉那一节
- **示例代码必须可运行。** 虚假示例 = 文档腐败
- **过期内容必须删除。** 保留旧的 API 路径、旧字段名比不写更危险
- **同一个事实只在一个文档维护。** 发现重复 → 合并承接方，其它地方引用
- **禁止 `-final` / `-v2` / `-new` 命名。** 无法判断真源的文档一律不允许长期存在

### 4.3 提交流检

```text
□ 测试全通过（bash scripts/ci-check.sh）
□ 文档已同步
□ 无死链（scripts/doc-link-check.sh）
□ 无 console.log / TODO / 英文注释
□ 变更范围与 diff 一致
```

### 4.4 Git 提交流程与提交信息格式（强制）

提交流程（copy 自 CoSense / love-lobster 的实际协作习惯）：

```text
1. 提交前先向用户展示改动清单并获得确认；
   同一批多个改动（多 bug / 多模块）→ 逐一组确认、逐一提交，不混在一个 commit。
   耦合文件（同一功能/布局必须一起提交）→ 先确定分组经确认后按组一次提交。
2. 一个 commit 只包含一个主题（一个功能 / 一个修复 / 一类文档变更），
   不混入无关改动；提交前确认 `git status` 与 diff 一致。
3. 仅提交到本地仓库；push 需用户明确指令，不得擅自 push。
```

提交信息格式（由 `.githooks/commit-msg` 强制校验，不合规直接拒绝提交）：

```text
类型: 中文描述

- 文件名/模块: 要点     ← 可选：主题行后空行，再以 bullet 逐项列改动明细

类型白名单: feat / fix / refactor / chore / docs / test / style / perf / ci / revert
dev-log 分支专用类型: dlog（仅用于 dev-log 分支的日志提交，不用于代码提交；消息必须描述实际工作内容，禁止「更新开发日志」类空话——钩子直接拒绝）
```

反例（会被 hook 拒绝）：

```text
fix(web): xxx          ← 类型后不加括弧说明
fix: fix login bug     ← 描述必须用中文
update something       ← 缺类型前缀
```

---

## 五、快速参考

### 5.1 技术栈（目标）

| 部分 | 技术栈 | 端口 |
|------|--------|------|
| `backend/` | FastAPI + Pydantic Settings + uv（Python 3.12）；SQLAlchemy 等适配器按阶段接入 | 4000 |
| `frontend/` | Vite + React（Phase 3 建立） | 3000 |
| 存储 | PostgreSQL 16 + pgvector（元数据 / 向量）、Neo4j（GraphRAG）、Redis（checkpoint / job 状态） | 5432 / 7474 / 7687 / 6379 |
| 编排 | LangGraph（分析工作流） | — |

### 5.2 常用命令

| 命令 | 说明 |
|------|------|
| `start.bat` | 一键启动（当前：dev-log 自动同步 + Docker 引擎自动拉起 + postgres/redis 容器启动与健康检验；依赖安装 / 前后端启动后续逐步加法） |
| `docker compose up -d` | 启动 PostgreSQL(pgvector) + Neo4j + Redis |
| `cd backend && uv run python -m app.infrastructure.collectors <路径>` | 采集本地 Git 仓库为 `SourceManifest`（步骤 3 采集 CLI，`--json` 输出规范 JSON） |
| `cd backend && uv run python -m app.infrastructure.analyzers <路径>` | 采集+分析一条链输出 `CodeGraph`（步骤 4 CLI，`--json` 输出规范 JSON） |
| `cd backend && uv run python ../eval/codegraph/validate.py <工件.json> --repo-root <仓库根>` | CodeGraph 产物三项不变量校验（DEFINES 入边 / content_hash 重算 / imports 目标；CI 经 pytest 强制执行） |
| `bash scripts/ci-check.sh` | **push 前全量检查**（文档死链 → 后端 lint/测试 → 前端 lint → 密钥扫描） |
| `bash scripts/doc-link-check.sh` | 仅检查文档死链 |
| 开发日志（查看/编辑） | 唯一真源在 `dev-log` 分支：worktree `D:\Project_Mine\InsightGraph\.devlog`；**口述给 AI 登记 / 完成即可**（`add/done` 为内部命令，人不需要记）；网页直读见其 DEV_LOG.md 头部链接 |
| `bash devlog.sh sync "<提交说明>"` | 在 devlog worktree 内运行：格式校验 → 提交 → pull --rebase → push（被拒自动重试；说明必填，add/done 自动派生消息） |
| `bash devlog.sh pull` | 仅拉取开发日志（不提交不推送；供 start.bat 启动时自动调用） |
| `git config core.hooksPath .githooks` | 一次性安装 Git Hooks（pre-commit / pre-push / commit-msg；新环境必须执行，main / dev 与 .devlog 工作树共用） |
| `cd backend && uv run ruff check app/` | 后端 Ruff（0 错误 hard gate，backend 建立后可用） |

### 5.3 当前代码-文档现实（实际状态地图 · 迁移中间态）

> **架构文档描述目标架构；本节描述代码当前实际状态。两者冲突时以本节为准。**
> 历史教训（来自 CoSense）：AI 依据“理想态文档”写码，看到目标模块还不存在后走旁路，
> 造成双实现并存。每完成一个阶段，更新本节。

| 资产 | 状态 | 说明 |
|------|------|------|
| `docker-compose.yml` + `docker/postgres/init.sql` | ✅ 就绪 | postgres/redis 已在本机启动并 healthy（2026-10-02）；neo4j 未启动；api、web 服务待代码建立后加入 |
| `.github/workflows/ci.yml` | ✅ 就绪 | docs 立即可用；backend / frontend 用存在性守卫，建立后自动生效 |
| `scripts/` + `.githooks/`（pre-commit / pre-push / commit-msg） | ✅ 就绪 | 需一次性安装：`git config core.hooksPath .githooks` |
| `eval/` | ✅ 首个 evaluator 已落地 | `eval/codegraph/`：Golden Dataset（golden-python-basic）+ evaluator（语义 100%）+ Baseline v1 |
| 开发日志（`dev-log` 分支） | ✅ 就绪 | 独立 orphan 分支为唯一真源；工作树 .devlog 自带钩子（校验 / 强制 dlog / 提交后自动推送）；devlog.sh sync / pull；CI 只读校验 + 7 天陈旧提醒；Setup 与启动自动 pull 已并入 start.bat |
| `backend/` | ✅ Phase 2A 骨架 | FastAPI + Settings + 错误/日志 + domain/application/infrastructure 分层 + 测试门禁 |
| `frontend/` | ⏳ 未建立 | Phase 3：Vite + React + 视觉回归双守卫 |
| CodeGraph / GraphRAG 领域契约 | ✅ 稳定版 | 稳定 ID、ScanResult/错误/统计契约、确定性序列化与 schema_version 已定（ADR-010/011）；Collector 与 Analyzer 已实现（步骤 3/4）；Repository 未实现 |
| LangGraph 工作流 | ⏳ 未建立 | `workflows/` 仅声明“编排不承载业务”的边界，尚未引入 LangGraph |
| 真实 LLM 评测 workflow | ⏳ 未建立 | Phase 3：手动触发 + gate 脚本（不进常驻 CI） |

### 5.4 模块速查（以代码实际目录为准）

| 模块 | 职责 | 关键文件 |
|------|------|----------|
| `api/` | HTTP 协议、请求校验和响应转换 | `api/router.py`、`api/health.py` |
| `application/scans/` | 编排 Collector、Analyzer 与 Repository 端口；扫描结果与错误契约 | `service.py`、`ports.py`、`models.py` |
| `domain/codegraph/` | CodeGraph IR、稳定 ID 构造与持久化端口 | `models.py`、`ids.py`、`kinds.py`、`ports.py` |
| `domain/evidence/` | Evidence 来源与可信状态 | `models.py` |
| `domain/graphrag/` | 知识节点与 Evidence First Claim | `models.py` |
| `infrastructure/` | Collector、Analyzer、Persistence、LLM 外部适配器 | `collectors/`（步骤 3）与 `analyzers/`（步骤 4）已实现；`analyzers/entry_points.py` 为步骤 5 先行件（仅识别，表示层待定）；Persistence/LLM 未建立 |
| `workflows/` | LangGraph 编排入口 | 当前仅建立边界 |
| `foundation/` | 配置、日志与统一错误处理 | `config.py`、`logging.py`、`errors.py` |

### 5.5 文档索引

| 文档 | 说明 |
|------|------|
| [docs/README.md](docs/README.md) | 文档入口与维护规则 |
| [docs/Standards.md](docs/Standards.md) | 仓库信息、目录约定、版本控制约定 |
| [docs/architecture.md](docs/architecture.md) | 系统架构真源：当前状态、边界、数据流与演进路线 |
| [docs/初始化架构思想导论.md](docs/Introduction%20to%20Initialization%20Architecture%20Concepts.md) | Evidence First、依赖倒置、双图分离与确定性优先 |
| [docs/Development Plan.md](docs/Development%20Plan.md) | 0～10 建设顺序、完成门槛、当前进度与下一步行动 |
| [docs/InsightGraph_Engineering Infrastructure.md](docs/InsightGraph_Engineering%20Infrastructure.md) | 工程基础设施借鉴方案（v2 · 证据版）——CI / Docker / 评测 / 文档治理全部细则 |
| [docs/adr/README.md](docs/adr/README.md) | 架构决策记录（模板 + 首批清单） |
| [eval/README.md](eval/README.md) | 评测目录规则（Baseline / Golden） |
