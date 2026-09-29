# InsightGraph 工程基础设施借鉴方案（v2 · 证据版）

> 目标：从 CoSense 项目（仓库 `love-lobster`）中筛选适合 InsightGraph 复用的工程基础设施，仅关注工程地基，不迁移 CoSense 的业务域设计。
>
> 方法：v2 版本的全部结论来自对 `D:\Project_Mine\Love-lobster\love-lobster` 的逐文件真实读取（2026-09-29）。每个借鉴项标注来源文件；与 v1 的推测性描述不一致处已修正。
>
> 当前阶段：InsightGraph 仓库初始化完成；本方案对应的 **Phase 1 基础设施已落地**（见 §20、§21），backend / frontend 代码骨架尚未建立。
>
> 核心边界：
>
> - **CodeGraph**：负责分析仓库内部的函数、类、模块、导入关系、调用链和模块依赖。
> - **GraphRAG**：负责组织技术概念、项目能力、文档证据、代码证据以及它们之间的关系。
>
> 两者必须保持职责分离。GraphRAG 可以引用 CodeGraph 节点，但 CodeGraph 不承担项目技术事实推理。

---

## 1. 当前结论

InsightGraph 当前最值得借鉴的不是 CoSense 的业务代码，而是它在一个真实、长期、AI Agent 深度参与的项目中迭代出来的工程基础设施。

| 优先级 | 基础设施 | InsightGraph 落地方向 | love-lobster 证据（来源文件） |
| --- | --- | --- | --- |
| P0 | `CLAUDE.md` / AI 编码规则 | 仓库级 AI 开发约束 | `CLAUDE.md`（334 行，六大部分） |
| P0 | CI 质量门禁 | Ruff / Pytest / ESLint / 架构测试 | `.github/workflows/integration-tests.yml`、`.gitee/workflows/ci.yml` |
| P0 | 测试基础设施 | mock-first 单测 + 集成测试开关 | `app/tests/conftest.py`、`scripts/ci-test.sh`、`docker-compose.ci.yml` |
| P0 | Docker Compose | PostgreSQL/pgvector + Neo4j + Redis | `docker-compose.yml`、`app/entrypoint.sh` |
| P0 | 配置与密钥管理 | `.env.example` + fail-fast | `app/.env.example`、compose 的 `${VAR:?}` 强制变量 |
| P0 | 文档真源治理 | `docs/README.md` + 治理手册 | `docs/GOVERNANCE.md`、`docs/README.md`、CLAUDE.md §3.1 |
| P1 | Git Hooks + 本地检查 | pre-commit / pre-push / ci-check | `.githooks/`、`scripts/ci-check.sh`、`scripts/doc-link-check.sh` |
| P1 | Baseline First 评测 | 分层评测 + 回归门禁 | `docs/development/evaluation-driven-development.md`、`app/scripts/quality_eval/gate_quality.py` |
| P1 | 视觉回归 | 双守卫（数值断言 + 截图基线） | `web/e2e/visual.spec.ts`、`web/scripts/smoke-visual-diff.mjs` |
| P2 | 部署自动化 | MVP 稳定后引入 | `scripts/deploy.sh`、`scripts/webhook-server.py`（暂不迁移） |

与 v1 的重要修正：

```text
1. CI 中的评测（evaluation）不是常驻门禁，而是独立的手动触发 workflow
   （promptfoo-regression.yml，workflow_dispatch）——真实 LLM 调用有成本与波动，
   不放在每次 push 上。

2. pre-commit 只做「文档死链检查」，不做 lint 与格式化；
   安全门禁（硬编码扫描）在 scripts/ci-check.sh 里，作为 push 前全量检查的一部分。

3. love-lobster 同时托管 GitHub 与 Gitee（双 CI：actions + Gitee Go）。
   InsightGraph 当前只有 GitHub 远程，先只建 GitHub Actions。

4. 前端 vitest 不在 CI 的硬门禁里（ci-check.sh 只跑 tsc / eslint / mypy / ruff / pytest）；
   vitest 与 Playwright 视觉回归靠本地与约定执行。
```

---

## 2. CLAUDE.md：仓库级 AI 开发约束

InsightGraph 从第一天就建立根目录 `CLAUDE.md`（已落地）。

CoSense 的经验表明，`CLAUDE.md` 不应只是开发说明，而应作为 AI Agent 和代码生成工具的仓库级行为约束。

### 2.1 love-lobster 的实证结构（六部分）

```text
一、动手前（Pre-Flight，强制）
    · 先读 CLAUDE.md（本文是所有行为的入口）
    · 变更范围声明（动笔前一句话声明波及哪些文件，即 checklist）
    · 动态文档维护（发现文档腐败立即修，不作为独立任务）
    · 核心变更评测门禁（Baseline First → Same Eval → Delta Required）
    · 死链零容忍

二、编码规范
    · 硬性规范（违反 = review 打回）：结构化输出必须用 Pydantic、
      Provider 路由必须用 registry、所有 LLM 调用走 gateway、
      严禁循环 import、禁止跨模块 import 私有符号、
      禁止版本号文件名（XxxV2）、注释必须用中文
    · 弹性规范（新代码遵守、存量逐步消化）：
      模块大小阈值（Router ≤80 行 / ≤150 硬上限；Service ≤800 / ≤1000）、
      测试策略（bug fix 必须先写测试复现）、事务一致性模式
    · 「顺手还债清单」：明确标注"不是主动追杀清单"，
      防止 Agent 借「清理」之名改坏代码

三、完成后（Post-Task 文档同步，强制）
    · 文档同步矩阵：每类代码变更 → 必须更新的文档（表格化）
    · 文档质量底线：不写"待补充"、示例必须可运行、过期内容必须删除、
      同一事实只在一个文档维护
    · 提交流检：□测试全通过 □文档已同步 □无死链 □无脏注释 □diff 一致

三点五、架构实际状态地图（迁移中间态）
    · 「文档描述目标架构；本节描述代码当前实际状态；两者冲突以本节为准」
    · 用表格列出每个模块的迁移状态（✅完成 / ⚠️残留 / 已下线勿恢复）
    · 写码红线清单（本仓库的收敛正殿、禁止复活的已删资产）

四、快速参考
    · 技术栈表 + 模块速查表 + 常用命令表 + 文档索引
```

### 2.2 三条关键教训（直接适用于 InsightGraph）

```text
教训一：上下文成本要分层。
    完整长规范放 docs/development/，CLAUDE.md 只保留约 10 行短门禁 +
    条件式阅读入口；不要每次会话无条件加载长文档。

教训二：文档必须区分「目标态」与「实际态」。
    CoSense 踩过的坑：AI 依据"理想态文档"写码，看到 capabilities 是空壳后
    走旁路、跨模块偷私有符号，造成双实现并存。
    InsightGraph 的 CLAUDE.md 从第一天就要有「当前代码-文档现实」一节。

教训三：约束要分级。
    硬性规范（打回级）与弹性规范（逐步消化级）必须显式分开，
    否则 Agent 会在"最佳实践"的名义下改坏存量代码。
```

### 2.3 InsightGraph 的 CLAUDE.md 约束内容（已写入根目录）

```text
1. CodeGraph 与 GraphRAG 必须严格区分。

2. CodeGraph 负责：
   - Function / Class / Module
   - IMPORTS / CALLS / DEFINES
   - 代码入口 / 模块依赖

3. GraphRAG 负责：
   - Technology / Concept / Capability
   - ProjectClaim
   - DocumentEvidence / CodeEvidence
   - Evidence Relationship

4. 禁止把 CodeGraph 节点直接等同于 GraphRAG 知识节点。

5. 所有“项目具备某能力”的结论必须附 Evidence。

6. 没有直接证据时必须标记：
   - inference
   - hypothesis
   - unsupported

7. Router 不写业务逻辑。

8. Collector、CodeAnalyzer、GraphBuilder、Reviewer、Reporter
   必须通过明确的数据结构传递结果。

9. 禁止 Agent 绕过统一 Repository / Evidence Store。

10. 新增分析能力必须同步补充：
    - test
    - evidence schema
    - evaluation case
    - documentation
```

并保留 v1 的这段（CoSense 已验证的工作方式）：

```text
架构文档描述的是当前真实系统，而不是理想设计。

如果：
文档 != 代码

则：
以代码真实状态为准，并更新文档。
```

---

## 3. CI：建立真正有效的质量门禁

### 3.1 love-lobster 的实际 CI 布局（三个文件，职责不同）

```text
.github/workflows/integration-tests.yml
├─ job: integration-tests（30 分钟超时）
│   ├─ services: postgres:16-alpine + redis:7-alpine（带 healthcheck 参数）
│   ├─ uv 安装（astral-sh/setup-uv）+ Python 3.12
│   ├─ uv sync --group dev
│   ├─ 等待 PostgreSQL / Redis 就绪（轮询脚本）
│   ├─ alembic upgrade head
│   ├─ pytest --run-integration -m integration（junitxml 输出）
│   ├─ 全量测试（unit + integration，if: always()）
│   └─ 上传 test-results artifact（retention 14 天）
└─ job: lint（10 分钟超时，硬门禁）
    ├─ Ruff check（0 错误）
    ├─ Vulture 死代码检查（min-confidence 90）
    ├─ pnpm install --frozen-lockfile
    └─ ESLint（0 警告）

.github/workflows/promptfoo-regression.yml
└─ workflow_dispatch 手动触发（真实 LLM 调用，有成本）
    ├─ 输入：judge_model / tolerance
    ├─ 运行 quality_eval 金标评测
    └─ gate_quality.py 基线比对门禁（tolerance 默认 0.05）

.gitee/workflows/ci.yml
└─ Gitee Go 镜像 CI（push 到 dev / main / front 触发）
    ├─ ruff check
    └─ pytest（带 --ignore 已知损坏测试列表）
```

### 3.2 InsightGraph 的 CI（已落地）

`.github/workflows/ci.yml`，三个 job：

```text
docs     → 文档死链检查（bash scripts/doc-link-check.sh）—— 立即可用
backend  → 检测 backend/pyproject.toml 存在后：
           uv sync → ruff check → pytest（mock 单测，不依赖 PG/Redis）
frontend → 检测 frontend/package.json 存在后：
           pnpm install → lint → tsc -b
```

设计要点（吸取 love-lobster 经验）：

```text
1. 门禁必须「真的会红」：ruff / eslint 均为 0 容忍硬门禁。
2. 真实 LLM 评测不进常驻 CI，独立手动触发（Phase 2 落地 evaluation.yml）。
3. 代码尚未存在的阶段用「存在性守卫」让 CI 立刻可用且全绿，
   而不是先造一个必然失败的空壳 CI。
4. 前端类型检查命令用 `tsc -b`，不要写 `pnpm build --noEmit`——
   CoSense 曾因 --noEmit 被转发给 vite 导致该步骤恒红、从未真正校验
   （2026-09-23 修复，教训留档于其 ci-check.sh 第 31-34 行注释）。
```

### 3.3 特别增加：CI Self-Test

一个容易被忽略的问题是：

> CI 本身也可能是坏的。

因此建议增加一组专门验证门禁是否真的有效的 fixture。

例如：

```text
tests/ci-fixtures/

ruff-error/
pytest-error/
typescript-error/
missing-evidence/
broken-golden/
```

验证：

```text
ruff 真会失败
pytest 真会失败
tsc 真会失败
Evidence 缺失真会报错
Golden Regression 真会阻断
```

不要只验证产品代码，也要验证“验证工具本身”。

---

## 4. 测试基础设施：mock-first 单测 + 集成测试开关（v2 新增）

这是 love-lobster 测试体系中最值得整体迁移的部分，v1 未展开。

### 4.1 conftest.py 的 mock-first 策略

`app/tests/conftest.py` 的核心设计：

```text
1. 「在任何 app 模块 import 之前」patch sqlalchemy create_async_engine，
   并用 mock engine 顶替 —— 默认全量单测不需要 PostgreSQL / Redis；
2. APP_ENV=test、JWT_SECRET、REDIS_URL 等在 import 前通过 os.environ 注入；
3. 聚合 import 全部 ORM 模型（保证 mapper 配置完整），避免测试顺序
   造成 sqlalchemy 初始化失败污染整个 pytest 进程；
4. mock Redis 用 fakeredis（autouse fixture）；
5. 自定义 CLI 开关 --run-integration：开启时解除 patch，改用真实数据库；
6. pytest 标记 @pytest.mark.integration 的测试默认 skip。
```

### 4.2 统一测试入口脚本

`scripts/ci-test.sh` 三种模式：

```bash
bash scripts/ci-test.sh           # 默认：全量（跳过 BROKEN_FILES 列表）
bash scripts/ci-test.sh --quick   # 仅单测（-m "not integration and not slow"）
bash scripts/ci-test.sh --all     # 含已知损坏测试（期望失败，用于排查）
```

`BROKEN_FILES` 数组是「已知损坏测试」的显式清单，注释写明"全部修复后此列表应为空"——已被修复的测试必须从列表移除，不允许长期挂着。

### 4.3 集成测试基础设施脚本

`scripts/ci-integration.sh` 的编排（直接可复用的模式）：

```text
1. 前置检查 Docker / docker compose 可用（exit code 2 区分环境问题）
2. 启动 docker-compose.ci.yml（-p 独立项目名，避免污染开发容器）
3. trap cleanup EXIT —— 保证中断也能清理（--no-clean 可保留调试）
4. 轮询等待 PostgreSQL / Redis 健康（超时输出容器日志后退出，exit code 3）
5. alembic upgrade head（--skip-migrate 可跳过）
6. pytest --run-integration
7. 退出码：0 全过 / 1 测试失败 / 2 Docker 不可用 / 3 基础设施启动失败
```

`docker-compose.ci.yml` 与开发 compose 分离的关键差异：

```yaml
# 测试库用内存盘 + 快速健康检查 + 不持久化
postgres:
  tmpfs: /var/lib/postgresql/data
  healthcheck: { interval: 3s, retries: 10 }
redis:
  tmpfs: /data
  command: redis-server --appendonly no
```

### 4.4 两条用血换来的教训（务必继承）

```text
教训一：跨测试污染。
    裸 asyncio.run() 会污染 pytest session 事件循环，导致 985 项假失败
    （整模块一起挂、单跑却过）。
    → 看到这种模式先怀疑污染，不要改断言。

教训二：A/B 对比必须预热。
    两个场景固定顺序串行跑时，第一个场景独吞冷启动成本，
    测出来的是执行顺序而不是性能差异。
    → 任何"A vs B 谁快"的测量，先跑 1-2 轮预热并丢弃。
    （该教训来自 love-lobster 评测系统，对 InsightGraph 的
     CodeGraph/GraphRAG 评测同样成立。）
```

### 4.5 数据库迁移卫生

```text
1. entrypoint 强制检查「恰好 1 个 alembic head」，多于 1 个直接拒绝启动
   （迁移分支必须合并后再部署），绝不自动 stamp 跳过迁移。
2. alembic_version.version_num 默认 VARCHAR(32)；当 revision id 超过 32 字符，
   全新库初始化会中断。love-lobster 的解法是在 init.sql 中按 VARCHAR(64) 预建
   （表已存在时 Alembic 直接沿用，不比较列宽）。
   → InsightGraph 用短 revision id 规范（≤32 字符）从源头规避；
     若未来出现同类问题，参考 docker/postgres/init.sql 中留档的解法。
```

---

## 5. Docker Compose

### 5.1 love-lobster 的实证细节

`docker-compose.yml` 中值得直接继承的实践：

```text
1. 数据库用 pgvector 官方镜像：pgvector/pgvector:pg16（语义检索开箱即用）。
2. 每个服务都有 healthcheck，且 app 用 depends_on: condition: service_healthy
   串联启动顺序（不是简单的 depends_on）。
3. 关键密钥用 ${VAR:?错误信息} 强制显式提供（缺失即拒绝启动），
   开发弱默认值只用于非敏感项。
4. 挂载 init.sql 到 /docker-entrypoint-initdb.d/（首次初始化自动执行）。
5. mem_limit 逐服务限制（postgres 512M / redis 256M / app 2G），
   防止单服务拖垮开发机。
6. 命名卷持久化（postgres_data / redis_data），容器重建不丢数据。
7. healthcheck 用容器内自带的探测命令（pg_isready / redis-cli / python urllib），
   不引入额外工具。
```

`app/Dockerfile` 的分层与缓存策略：

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# 系统依赖（稳定层）→ 依赖文件（缓存层）→ 应用代码（高频变更层）
COPY pyproject.toml uv.lock* ./
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/
RUN uv sync --no-dev
COPY . .
ENTRYPOINT ["/entrypoint.sh"]   # 自动迁移 DB 后启动 uvicorn
```

### 5.2 InsightGraph 的落地（已创建）

`docker-compose.yml`（仓库根）：

```text
services:
  postgres  → pgvector/pgvector:pg16，挂载 docker/postgres/init.sql，
              命名卷 + healthcheck + mem_limit
  neo4j     → neo4j:5.26-community（LTS），NEO4J_AUTH，
              cypher-shell healthcheck
  redis     → redis:7-alpine，appendonly + maxmemory 策略

api / web 服务在 backend / frontend 建立后加入（需要 Dockerfile）。
```

职责建议如下。

## PostgreSQL + pgvector

存储：

```text
Repository Metadata
Research Task
Document Chunk
Embedding
Evidence Metadata
Report Metadata
LangGraph 持久化信息
```

## Neo4j

主要承担：

```text
GraphRAG
```

例如：

```text
Technology
Concept
Capability
ProjectClaim
DocumentEvidence
CodeEvidence
```

## Redis

第一阶段只承担必要的临时能力：

```text
LangGraph checkpoint
Job State
Rate Limit
Temporary Cache
Task Progress
```

不要一开始把 Redis 扩展成复杂业务状态中心。

---

## 6. 配置与密钥管理

### 6.1 love-lobster 的 `.env.example` 模式（实证）

`app/.env.example` 顶部是一段强制阅读的安全横幅：

```text
1. 此文件包含密钥模板，真实 .env 禁止提交到 Git（.gitignore 已忽略）。
2. 生产部署前必须替换所有占位密钥为强随机串：
   python -c "import secrets; print(secrets.token_urlsafe(48))"
3. API Key 禁止硬编码在前端代码、public/ 目录或 index.html 中。
4. 若怀疑密钥泄露，立即轮换所有密钥并审查 Git 历史。
```

以及多环境部署说明（开发 / 生产 / 测试三套 .env，deploy 脚本自动合并新增 key）与 Key Pool 模式（`DEEPSEEK_API_KEY_0/1/2/3` 加权轮询，MVP 不需要，留作天花板参考）。

### 6.2 InsightGraph 的落地（已创建）

根目录 `.env.example` 分四段：安全横幅 → 基础设施（compose 变量）→ 后端应用（规划中）→ 缺失即拒绝启动清单。

后端统一通过 Pydantic Settings 管理。

例如：

```python
class Settings(BaseSettings):
    github_token: str | None

    database_url: str

    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    redis_url: str

    llm_provider: str
    llm_api_key: str
```

启动时进行 fail-fast。

例如：

```text
DATABASE_URL 缺失
→ 拒绝启动

NEO4J_PASSWORD 缺失
→ 拒绝启动

生产环境 DEBUG=true
→ 拒绝启动

LLM Provider 配置不完整
→ 拒绝启动
```

同时加入 Secret Scan。

重点防止以下内容进入 Git：

```text
GITHUB_TOKEN
OPENAI_API_KEY
DEEPSEEK_API_KEY
QWEN_API_KEY
NEO4J_PASSWORD
DATABASE_PASSWORD
```

love-lobster 在 `scripts/ci-check.sh` 里落地的扫描实例（可参考的写法）：

```text
1. 硬编码 Redis key 扫描：正则匹配源码中的 'session:'、'user:'、'match:' 等
   前缀字符串字面量，命中即 fail（应走常量或配置管理）。
2. Router 越权扫描：遍历所有 router.py，有 @router. 装饰器但文件内
   没有 get_current_user 的模块告警（auth 模块与健康检查除外）。
```

→ InsightGraph 对应版本：扫描 `backend/app/` 与 `frontend/src/` 中疑似密钥字面量（`sk-`、`ghp_`、`AKIA` 等模式）与 `.env` 误提交。

MVP 阶段可以继续使用 `.env`。

但设计上不要依赖硬编码配置，为未来：

```text
GitHub Secrets
Docker Secrets
Vault
KMS
```

预留迁移空间。

---

## 7. CodeGraph 与 GraphRAG 的数据边界

这是 InsightGraph 最重要的架构边界之一。

推荐：

```text
Repository
   │
   ├── CodeGraph IR
   │      ├── Function
   │      ├── Class
   │      ├── Module
   │      ├── CALLS
   │      ├── IMPORTS
   │      └── DEFINES
   │
   └── Evidence Extraction
          │
          ▼
        GraphRAG
          ├── Concept
          ├── Technology
          ├── Capability
          ├── ProjectClaim
          ├── DocumentEvidence
          └── CodeEvidence
```

核心原则：

```text
CodeGraph = 程序分析图

GraphRAG = 研究证据图
```

GraphRAG 可以引用 CodeGraph。

例如：

```json
{
  "type": "CodeEvidence",
  "file_path": "app/services/parser.py",
  "symbol_id": "RepositoryParser.parse",
  "line_start": 42,
  "line_end": 86,
  "codegraph_node_id": "func:RepositoryParser.parse"
}
```

但禁止直接把：

```text
Function
Class
Module
```

全部强行转成 GraphRAG 的知识实体。

否则 Neo4j 很容易逐渐退化成一张“什么都放”的万能图。

---

## 8. Baseline First：InsightGraph 的核心研发方法

建议从项目第一阶段就采用：

```text
Baseline
    ↓
Change
    ↓
Same Eval
    ↓
Delta
```

不要采用：

```text
改完代码
↓
感觉效果不错
↓
合并
```

### 8.1 love-lobster 规范的完整机制（`docs/development/evaluation-driven-development.md`）

```text
1. 核心变更定义：AI/LLM 行为、召回排序、信息提取、评分阈值、
   关键性能、会明显改变用户结果的交互……均属 Core Change；
   判断不了时按 Core Change 处理。

2. 修改前门禁六问：
   当前能力和生产代码路径？可重复评测入口？固定 Dataset 与 Gold 版本？
   当前 Baseline 与原始输出存放位置？本次改善哪个 Primary Metric？
   哪些 Guardrail 不能退化？

3. 最小基线记录（JSON）：
   feature / dataset_version / git_sha / timestamp / runner /
   model_or_algorithm / metrics{primary, guardrail} / raw_outputs

4. 汇报格式（强制）：
   Before → After → Delta → Regression（新增失败 case / 已修复 case / 剩余风险）
   不能只展示变好的案例。

5. 完成口径：
   缺少 Baseline 或 After Evaluation 时只能写「实现完成，评测未完成」，
   不能写「优化完成」。

6. 禁止事项清单（10 条）：编造 Baseline、比较时换 Dataset、
   只挑好案例、删除失败样本、AI 自称 Gold、复制生产逻辑做测试实现、
   为每个功能开长期端口、把 Harness 通过等同于产品效果提升……

7. 紧急例外：安全/数据损坏可先止血，但必须记录跳过门禁的原因与补评测计划。
```

### 8.2 工程侧的配套（实证）

```text
1. gate_quality.py —— 回归门禁脚本：
   读取最新评测报告 JSON，与基线比对，超过 tolerance（默认 0.05）即失败。
   手动 workflow 触发时 tolerance 可传入。

2. 优先级：先复用现有评测入口，再新建最小 Harness：
   love-lobster 已有 quality_eval / eval_hub / intent_eval / memory_eval
   四个入口 + start-eval.bat 一键看板；
   明确禁止「为评测复制一套与生产逻辑不同的实现」。

3. eval_hub 的统一化模式：
   registry（注册评测类别）→ runner（运行）→ normalize（指标归一化）
   → server + dashboard.html（看板）。
   InsightGraph 的评测数量增长后可以借鉴这个「注册表 + 归一化」结构。
```

推荐建立（InsightGraph 版）：

```text
eval/
├─ codegraph/
│  ├─ cases/
│  ├─ baselines/
│  └─ evaluator.py
│
├─ retrieval/
│  ├─ cases/
│  ├─ baselines/
│  └─ evaluator.py
│
└─ report/
   ├─ cases/
   ├─ baselines/
   └─ evaluator.py
```

（`eval/README.md` 骨架已创建，规则见 §12。）

---

## 9. CodeGraph Evaluation

主要回答：

> CodeGraph 有没有正确理解代码结构？

第一批指标：

```text
Function Detection Accuracy
Class Detection Accuracy
Module Detection Accuracy
Import Edge Accuracy
Call Edge Accuracy
Entry Point Accuracy
Symbol Location Accuracy
```

Golden Case 可以手工挑选几个典型仓库。

例如：

```text
FastAPI 项目
React 项目
LangGraph 项目
Python CLI 项目
Monorepo
```

### 9.1 v2 新增：消融臂设计（来自 love-lobster 图谱证据块评测）

love-lobster 的 memory_eval「图谱证据块」评测设计了一套可直接迁移的实验结构：

```text
四臂消融：hop0_only / hop0_hop1 / full / full_no_gate
—— 同 Dataset / Gold / Metrics 各跑一遍：
   A vs C 证明「图遍历」带来增量；
   C vs D 证明「门控」在起作用（若 C==D，说明门控没接上）。

0 容忍断言：为每类确定性错误（编造引用 / 越权 / 过期数据……）
设计 ≥5 正例 + 5 反例，出现一条即失败。

dropped 载体：每条「为什么这条没出现」必须可查——
否则漏放会静默通过。
```

对应到 CodeGraph 评测：

```text
1. 消融臂可以是：regex-only / regex+AST / full parser(+调用图)；
   比较每层带来的 Detection Accuracy 增量。
2. 「找不到符号位置」这类失败必须是显式输出（可查为什么被丢），
   而不是静默缺失。
3. Golden 仓库的每个指标场景配正/反例，防止「只测 happy path」。
```

---

## 10. GraphRAG Evaluation

GraphRAG 的评测问题不是：

> 图建得漂不漂亮？

而是：

> 是否找到了支持某个结论的真实证据？

建议指标：

```text
Retrieval Hit@K
MRR
Evidence Recall
Evidence Precision
Multi-hop Retrieval Accuracy
Unsupported Evidence Rate
```

### 10.1 v2 新增：两条测量纪律（love-lobster 血泪教训）

```text
纪律一：配对采样。
    多策略对比时，每轮内紧挨着依次跑完所有泳道，分析逐轮配对差值，
    而不是两条独立曲线——配对能消掉负载/网络/缓存的时变噪声。

纪律二：小样本不谈 P95。
    P95 的稳定性由「超出 P95 的观测数」决定（服从 Binomial(n, 0.05)）；
    n=20 时 P95 基本等于最大两三个值的插值，不要把它设成门禁。
    样本不足时仍输出 P95，但必须标注样本量。
```

---

## 11. Report Evaluation

Reporter 最重要的目标是：

> 最终技术报告中的结论能否被回查。

建议建立核心指标：

```text
Evidence Coverage Rate
```

定义：

```text
Evidence Coverage Rate
=
有直接证据支持的关键结论
/
所有关键结论
```

另外建议：

```text
Citation Validity
Code Location Accuracy
Unsupported Claim Rate
Source Diversity
Evidence Conflict Detection Rate
```

其中：

```text
Unsupported Claim Rate
```

应该作为重点质量门禁。

---

## 12. Golden Dataset 规则

Golden / Baseline 不允许被普通代码修改自动覆盖。

推荐：

```text
eval/**/baselines/
```

遵守（love-lobster 的实证版本）：

```text
Baseline 只创建，不自动覆盖。

重写 Baseline 必须显式传参（--write-baseline），
不允许默认行为改写基线。

修改 Baseline：
必须独立 Commit。

修改 Golden：
必须人工审核 —— AI 可以生成候选样本与预标注，
但主观/语义类 Gold 必须由人确认。

PR 不允许因为当前实现失败而自动重写期望结果。

数据集确需调整时：升版本，并用新版本重新计算旧实现的 Baseline。
```

另一个实证细节（schema 污染教训）：

```text
每个能力用「独立的 baseline 文件」，不要混入其它评测的 schema——
love-lobster 曾把 provider_latency 基线塞进 quality_main 的基线文件，
污染了归一化读数，后拆成独立文件。
```

否则评测会失去意义。

---

## 13. Git Hooks 与本地质量门禁

### 13.1 love-lobster 的实际 hooks（比 v1 描述更收敛）

```text
.githooks/pre-commit
└─ 只做一件事：bash scripts/doc-link-check.sh（文档死链检查）

   安装方式（一次性）：
   git config core.hooksPath .githooks

.githooks/pre-push
└─ 仅当推送到 dev / main / front 分支时运行 scripts/ci-test.sh
   跳过方式：SKIP_TESTS=1 git push
   feature 分支不强制。
```

注意：lint / 类型检查不在 hook 里跑（太慢），它们在 `scripts/ci-check.sh`（push 前手动全量检查）与 CI 里。

### 13.2 scripts/ci-check.sh —— 本地全量检查的实证结构

```text
[1/7] Frontend TypeScript 类型检查    （pnpm exec tsc -b）
[2/7] Frontend ESLint（0 警告 hard gate）
[3/7] Backend MyPy 类型检查
[4/7] Backend Ruff lint（0 错误 hard gate）
[5/7] Backend Mock 模式测试（pytest -m "not integration"）
[6/7] Security — 硬编码 Redis key 检查（正则扫描源码字面量）
[7/7] Security — Router 越权检查（无 auth 保护的端点告警）

每步 PASS/FAIL 着色输出；最终汇总；有任一失败 exit 1。
```

### 13.3 InsightGraph 的落地（已创建）

```text
.githooks/pre-commit   → scripts/doc-link-check.sh
.githooks/pre-push     → scripts/ci-check.sh（仅 main / dev；SKIP_TESTS=1 旁路）
.githooks/commit-msg   → 提交信息格式强制校验（类型: 中文描述；
                          白名单 + 中文描述 + 禁止括弧，不合规直接拒绝提交）

scripts/doc-link-check.sh
└─ 检查 docs/**.md + CLAUDE.md + README.md + README_cn.md 中
   所有相对链接可达（跳过 http/https、锚点、mailto；支持 %20 解码）。

scripts/ci-check.sh
├─ [1] 文档死链检查（始终执行）
├─ [2] Backend：若 backend/ 存在 → ruff check + pytest（mock 单测）
├─ [3] Frontend：若 frontend/ 存在 → eslint + tsc -b
└─ [4] Security：扫描 backend/app 与 frontend/src 中的疑似密钥字面量
```

不要在 pre-push 跑完整真实 LLM Evaluation。

真实模型测试可以放到：

```text
GitHub Actions Manual Trigger
```

避免每次 push 都产生成本和随机波动。

---

## 14. 文档真源治理

### 14.1 love-lobster 的实证机制（`docs/GOVERNANCE.md`）

```text
1. 文档分级（更新容忍度显式化）：
   P0 核心：Agent 每次任务必读（CLAUDE.md / docs/README.md / GOVERNANCE / CHANGELOG）
            → 不可过时
   P1 接口：外部可见契约（API / ER 图 / 前端架构 / 环境变量 / Redis Key）
            → 变更即时更新
   P2 架构：内部设计决策 → 模块变更时更新
   P3 记录：CHANGELOG → 版本发布时更新
   P4 产品 / P5 开发规范 → 对应变更时更新

2. 新建文档的准入：只有 P0/P1 新模块、战略评审报告、CHANGELOG 条目三类允许；
   临时调试 / 个人笔记禁止建文档（写进 CHANGELOG 或 commit message）。

3. 目录归属规则：新建文档必须进标准目录之一
   （architecture / product-specs / operations / development）。

4. 废弃规则：文件头加横幅标记 + README 移到「已废弃」+ 更新所有引用 +
   不删除文件（保留历史上下文）。

5. 新鲜度检查：文件头「最后更新」> 30 天 → 静态检查；
   引用路径不存在 → grep 确认；声称的端点/模型仍在代码中 → 抽样验证。

6. 死链检测自动化：doc-link-check.sh + pre-commit hook（见 §13）。
```

### 14.2 InsightGraph 的落地（已创建）

```text
docs/README.md
└─ 文档入口与索引：现有文档 + 规划分类（architecture/ engineering/ evaluation/ adr/）
   + 维护规则摘要（真源唯一、禁止 final/v2 命名、死链零容忍）+
   指向 CLAUDE.md 文档同步矩阵。

docs/adr/README.md
└─ ADR 模板（Context / Decision / Alternatives / Consequences / Status）
   + 首批建议清单。
```

职责：

```text
docs/README.md
= 文档入口

architecture.md
= 当前系统真实状态（目标态）

ADR
= 为什么这么设计

CLAUDE.md
= 开发行为规则

README.md
= 面向使用者的项目介绍
```

禁止长期出现：

```text
architecture-final.md
architecture-v2.md
architecture-new.md
architecture-new-final.md
```

这种无法判断真源的文档。

---

## 15. ADR：记录关键架构决策

建议新增：

```text
docs/adr/
```

第一批可以直接写：

```text
ADR-001-codegraph-vs-graphrag.md

ADR-002-postgres-vs-neo4j.md

ADR-003-langgraph-as-orchestrator.md

ADR-004-evidence-first-reporting.md

ADR-005-local-first-repository-analysis.md
```

ADR 记录：

```text
Context
Decision
Alternatives
Consequences
Status
```

以后你自己回看项目时，会非常有价值。

（`docs/adr/README.md` 模板已创建。）

---

## 16. 视觉回归

### 16.1 love-lobster 的「双守卫」体系（实证，核心是分工）

```text
数值断言（web/scripts/smoke-*.mjs）
└─ 抓「该变的变了没」：改了 token 是否真的生效。
   实现方式：真实浏览器（Playwright 无头）实测 computed style / DOM 几何 /
   像素差分（smoke-visual-diff.mjs），输出结构化读数。

截图基线（web/e2e/visual.spec.ts + snapshots/）
└─ 抓「不该变的变了没」：没动首页，首页像素有没有漂。
   实现方式：Playwright toHaveScreenshot + 基线快照。
```

两条守卫互补，缺一条就有一类问题没人抓。

### 16.2 基线纪律（实证，务必继承）

```text
1. 基线吃环境（OS / 浏览器版本 / 字体 / DPR 都会影响像素）：
   基线只在一台机器上生成与比较；换环境后 --update-snapshots 重建，
   并在提交信息里写明是环境变化导致。

2. 改动任何 token / 主题 / 样式「之前」先跑一遍确认基线是绿的；
   改完再跑，把 Before / After / Delta 写进提交信息。

3. 基线页面只收「无需业务状态、任何环境都能独立渲染」的路由；
   API 一律 mock 成确定态；随机动画（如随机位置的引导角色）不进基线。

4. 持续闪烁的装饰层用 mask 排除，但要连区域一起遮干净，别遮掉正文。

5. 不能只靠 animations: 'disabled'——JS 驱动动效需额外等待落定
   （waitForTimeout），再截图。

6. 禁止仅用「更像了」「视觉看起来正常」作为验收结论。
```

如果 InsightGraph 后续有 Web UI，建议加入视觉回归。

主要覆盖：

```text
Repository Overview
Module Dependency Graph
Function Call Graph
GraphRAG Graph
Research Report
Evidence Side Panel
Source Code Viewer
```

并采用：

```text
DOM / 数值断言
+
Screenshot Baseline
```

双轨验收。

不能使用：

```text
“感觉差不多”
“视觉看起来正常”
```

作为验收标准。

---

## 17. LLM Gateway

InsightGraph MVP 不需要复制大型 LLM Gateway。

但至少要抽象统一接口。

例如：

```text
LLMClient Protocol
      │
      ├── OpenAIAdapter
      ├── DeepSeekAdapter
      └── QwenAdapter
```

不要出现：

```text
collector.py
reviewer.py
reporter.py
```

各自：

```python
client = OpenAI(...)
```

否则未来模型切换和 A/B Evaluation 会变得非常困难。

建议所有模型调用统一经过：

```text
backend/app/llm/
```

### 17.1 love-lobster 网关的实证经验（值得继承的部分）

```text
1. Provider 路由用 registry：新 provider 只改注册 + 配置，不动路由代码。
2. 网关统一降级链；任何失败不得阻塞主流程（如「森森即时反馈」失败一律
   静默 suppress 落兜底）——对 InsightGraph 的分析链路同样适用：
   单个 LLM 调用失败应降级为「无推断结果」并标记 unsupported，
   而不是让整个分析任务崩掉。
3. 能力判定不要用「模型名含 vl/vision」这类启发式：
   love-lobster 曾误杀 deepseek-flash，修复方式是显式白名单。
4. 例外声明：embedding 服务不属于「LLM 生成调用」范畴（零计费 token、
   fail-open、独立熔断）——InsightGraph 也应把 embedding / rerank
   与生成式调用分开管理。
```

---

## 18. 版本固定与 Windows 开发脚本（v2 新增）

### 18.1 运行时版本固定（love-lobster 实证）

```text
.nvmrc            → 20          （Node 主版本固定）
.python-version   → 3.12        （Python 主版本固定）
.editorconfig     → UTF-8 / LF / 2 空格（Python 4 空格、bat CRLF、
                    markdown 不裁行尾空格）
.gitattributes    → * text=auto eol=lf；*.bat/*.cmd CRLF；
                    图片/字体/lock 标 binary
.prettierrc       → singleQuote / printWidth 100 / endOfLine: lf
.prettierignore   → 含 uv.lock、pnpm-lock.yaml、*.md
```

InsightGraph 现状：`.gitattributes` 已支持上述规则；`.editorconfig`、`.nvmrc`、`.python-version` 待 backend/frontend 建立时加入（已列入 Phase 2）。

### 18.2 Windows 开发便利脚本（love-lobster 实证清单）

```text
scripts/kill-port.ps1    释放指定端口（netstat + taskkill，区分 LISTEN 与
                         客户端连接，不会误杀代理进程）；kill-port.bat 包装
scripts/dev-backend.ps1  启动后端（自动清理端口）
start.bat / start.sh     一键安装依赖 + 启动前后端
start-eval.bat           启动评测看板（8001/8002/8003）
fix-db-and-deps.bat      修复 DB 与依赖（机器专属，gitignore 排除）
```

要点：

```text
1. 机器专属脚本（fix-db-and-deps.bat 等）必须写进 .gitignore，禁止提交。
2. .bat 首行 chcp 65001 >nul 处理中文输出编码。
3. PowerShell 脚本统一 -NoProfile -ExecutionPolicy Bypass 调用。
```

InsightGraph 现状：backend 建立后按此模式补齐 `scripts/dev-backend.ps1` 与 `scripts/kill-port.ps1`。

---

## 19. 不建议 MVP 阶段直接复制的 CoSense 资产

以下能力目前暂时没有必要完整搬进 InsightGraph（v2 按实际资产名收敛）：

```text
Gitee Webhook 自动部署（webhook-server.py + deploy-via-webhook.sh
+ webhook.Dockerfile + docker-compose webhook 服务）

deploy.sh 多环境部署脚本（dev / production / test 三套 env 合并）

Hermes 自动审查与合并（.hermes/config.md + hermes-merge/review 脚本，
依赖 Gitee PR 流程与云服务器部署）

LLM Key Pool 负载均衡（DEEPSEEK_API_KEY_0..3 加权轮询）

多 Worker Alembic 双层锁 / stamp 特例处理

capabilities DDD 四层（portrait/simulation/matching/report + registry）

evolution 自进化基建（ratchet / guide_learning / capsule 自动限流）

realtime_voice 实时语音（Qwen-Audio-Realtime 桥接）

大规模 Redis Pub/Sub / 复杂 SSE 多通道

微信登录 / OSS 存储 / 短信 Provider 抽象

87 个 SQLAlchemy 模型的拆分粒度
```

这些能力都是随着 CoSense 的业务规模逐渐产生的。

InsightGraph MVP 当前更重要的是：

```text
能运行

能验证

能追溯证据

能复现结果

能避免 AI Agent 绕架构

能确认每个结论来自哪里
```

而不是一开始建设成熟生产系统的全部复杂度。

---

## 20. 推荐仓库结构与当前落地状态

### 20.1 目标结构（综合 v1 推荐与 love-lobster 实证）

```text
InsightGraph/
│
├─ CLAUDE.md                        ✅ 已创建
├─ README.md / README_cn.md         ✅ 已填充（骨架简介）
├─ .env.example                     ✅ 已创建
├─ docker-compose.yml               ✅ 已创建（postgres/neo4j/redis）
├─ docker/
│  └─ postgres/init.sql             ✅ 已创建
│
├─ backend/                         ⏳ Phase 2（FastAPI + pyproject.toml）
│  └─ app/
│     ├─ api/
│     ├─ collectors/
│     ├─ codegraph/
│     ├─ graphrag/
│     ├─ workflows/
│     ├─ evidence/
│     ├─ reports/
│     ├─ llm/
│     └─ foundation/
│
├─ frontend/                        ⏳ Phase 2+（Vite + React）
│
├─ eval/                            ✅ 骨架（README.md，规则已定）
│  ├─ codegraph/
│  ├─ retrieval/
│  └─ report/
│
├─ tests/                           ⏳ 随 backend 建立
│  ├─ unit/
│  ├─ integration/
│  └─ architecture/
│
├─ docs/                            ✅ 已创建
│  ├─ README.md                     （文档索引与治理摘要）
│  ├─ architecture.md               （目标架构，草稿）
│  ├─ Standards.md                  （仓库信息与约定）
│  ├─ InsightGraph_Engineering Infrastructure.md（本文档）
│  ├─ adr/README.md                 （ADR 模板与首批清单）
│  ├─ engineering/                  ⏳ 需要时创建
│  └─ evaluation/                   ⏳ 需要时创建
│
├─ scripts/                         ✅ 已创建
│  ├─ doc-link-check.sh
│  └─ ci-check.sh
│
├─ .githooks/                       ✅ 已创建（需一次性安装）
│  ├─ pre-commit
│  ├─ pre-push
│  └─ commit-msg                    （提交信息格式强制校验）
│
└─ .github/
   └─ workflows/
      ├─ ci.yml                     ✅ 已创建
      └─ evaluation.yml             ⏳ Phase 2（手动触发，真实 LLM）
```

### 20.2 一次性安装命令（Git Hooks）

```bash
git config core.hooksPath .githooks
```

---

## 21. 当前推荐建设顺序

### Phase 1（✅ 本次完成）

```text
1. CLAUDE.md                      ✅
2. 文档真源治理（docs/README.md）  ✅
3. .env.example                   ✅
4. docker-compose.yml（+ init.sql）✅
5. GitHub Actions CI（ci.yml）     ✅
6. eval/ Baseline / Golden 骨架    ✅
7. Git Hooks + 本地检查脚本         ✅（doc-link-check + ci-check + commit-msg 格式校验）
```

### Phase 2（下一步）

```text
1. backend/ 骨架：FastAPI + Pydantic Settings（fail-fast）+ ruff/mypy/pytest 配置
   （直接照抄 love-lobster 的 pyproject.toml 分层：mypy 关闭 5 项注解债务检查、
   ruff E/W/F/I/UP/B/SIM、vulture 死代码检查）
2. tests/ 分层：conftest mock-first 策略 + --run-integration 开关（§4）
3. .nvmrc / .python-version / .editorconfig 补齐
4. LangGraph 主链路：

   Collector
       ↓
   CodeAnalyzer
       ↓
   GraphBuilder
       ↓
   Reviewer
       ↓
   Reporter
```

### Phase 3（能力上量后）

```text
frontend/（Vite + React）+ 视觉回归双守卫
eval 看板（借鉴 eval_hub 的 registry + normalize 结构）
evaluation.yml（手动触发真实评测 + gate 脚本）
部署自动化（MVP 稳定后再评估）
```

---

## 22. 最重要的架构约束

建议已经把下面这段写进根目录 `CLAUDE.md`（已落地）。

```text
# CodeGraph 与 GraphRAG 边界

CodeGraph 负责回答：

“代码是如何组织和调用的？”

包括：

- Function
- Class
- Module
- Import
- Call
- Dependency
- Entry Point

GraphRAG 负责回答：

“这个项目为什么被认为具备某种技术能力，
这个判断由哪些文档证据和代码证据支持？”

包括：

- Technology
- Concept
- Capability
- Claim
- Document Evidence
- Code Evidence

禁止将 CodeGraph 和 GraphRAG 合并成一个没有语义边界的万能图。

GraphRAG 可以引用 CodeGraph 节点。

CodeGraph 不承担项目技术事实推理。
```

---

## 23. InsightGraph 当前工程原则

最终可以归纳成六条：

```text
Evidence First
证据优先，而不是模型判断优先。

Code Is Truth
判断项目真实能力时，以代码和可验证资料为准。

Graph Separation
CodeGraph 与 GraphRAG 职责严格分离。

Baseline First
所有重要算法改动必须有 Before / After / Delta。

Fail Fast
配置错误、Schema 错误、Evidence 缺失尽早失败。

Reproducible Research
同一个 Repository + Version + Config
应能够复现相同的研究过程与证据链。
```

这六条可以作为 InsightGraph 后续开发的工程基础原则。

---

## 24. 当前不追求的东西

MVP 阶段暂时不以以下能力作为重点：

```text
超复杂 Agent 自治

大量微服务

全自动生产部署

极致横向扩展

复杂权限系统

多租户

完整企业级 Secret Infrastructure
```

优先保证：

```text
Repository
→ Collect
→ CodeGraph
→ Evidence
→ GraphRAG
→ Verify
→ Report
```

这一条链路正确、可验证、可追踪。

---

## 结论

InsightGraph 当前最应该从 CoSense 借鉴的不是其业务架构，而是它在一个真实项目中沉淀下来的这些能力：

```text
CLAUDE.md（含实际状态地图机制）
+
CI（硬门禁 + 手动评测）
+
测试基础设施（mock-first + 集成开关 + 污染防线）
+
Docker Compose（healthcheck 串联 + 资源限制）
+
Configuration（fail-fast + 安全横幅）
+
Git Hooks + ci-check（文档死链 + 安全扫描）
+
Document Governance（P0-P5 分级 + 死链检测）
+
Baseline / Golden（只建不覆盖 + 显式重写）
+
Evaluation Harness（配对采样 / 预热 / 消融臂 / 0 容忍断言）
+
Visual Regression（双守卫 + 基线环境纪律）
```

这些能力共同解决的核心问题不是“让代码更规范”，而是：

> 让一个由 AI Agent 大量参与开发和分析的项目，始终能够知道什么是真实代码、什么是模型推断、什么是直接证据，以及每一次修改究竟让系统变好了还是变差了。

这正是 InsightGraph 最需要的工程基础。

---

> 附：本文档中引用的 love-lobster 文件（供回查，均为 2026-09-29 读取版本）：
>
> ```text
> CLAUDE.md / CONTRIBUTING.md / .gitignore / .gitattributes / .editorconfig
> docker-compose.yml / docker-compose.ci.yml / app/Dockerfile / app/entrypoint.sh
> app/pyproject.toml / app/.env.example / app/alembic/init.sql
> app/tests/conftest.py
> scripts/ci-check.sh / ci-test.sh / ci-integration.sh / doc-link-check.sh / kill-port.ps1
> .githooks/pre-commit / pre-push
> .github/workflows/integration-tests.yml / promptfoo-regression.yml
> .gitee/workflows/ci.yml
> docs/GOVERNANCE.md / docs/README.md
> docs/development/evaluation-driven-development.md
> docs/engineering/visual-regression-driven-development.md
> web/package.json / web/playwright.config.ts / web/e2e/visual.spec.ts
> .hermes/config.md
> ```
