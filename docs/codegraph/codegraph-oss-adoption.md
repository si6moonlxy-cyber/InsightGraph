# CodeGraph OSS 快速落地选型：Adapter + 开源引擎路线

> 状态：步骤 5 选型与落地策略文档（供 Human 审核；引擎引入与契约变更须经 POC 证据 + 决策后实施）
> 日期：2026-10-04 ｜ 依据：Human feedback（`docs/codegraph/CodeGraph CALLS 前置调研 - feedback.md`）
> 关联：研究资料 [codegraph-calls-pre-research.md](codegraph-calls-pre-research.md)（§2 项目笔记 / §3 机制对比仍然有效；**其选型结论以本文为准**）、
> 系统架构 [architecture.md](../architecture.md)、契约 [ADR-010](../adr/ADR-010-codegraph-contract-discipline.md) / [ADR-011](../adr/ADR-011-scan-result-contract.md)
> 快照：本文所有许可证 / 维护 / 平台事实为 2026-10-04 实测（GitHub API + LICENSE 文件 + README/文档）。

## 1. 主要矛盾（重述）与验收定义

Feedback 修订后的主要矛盾：

> **借鉴和使用开源项目，快速开展 CodeGraph 代码解析功能。**

问题重新定义（feedback §五，本文采纳）：不是"我要实现 CALLS"，而是"**我要为 GraphRAG 得到足够可信、可追溯的代码关系**"。
可验收的事实集合（按产品能力定义）：

```text
FILE / MODULE / CLASS / FUNCTION / METHOD / IMPORT / CALL / CONTAINS / INHERITS / IMPLEMENTS / ENTRY_POINT
每条尽量携带：source_file + start_line + end_line + symbol + resolution（四态）
```

验收主线：

```text
OSS Engine（看懂代码）→ Canonical Adapter（统一语义与证据）→ 本仓库 CodeGraph Artifact → GraphRAG / API / UI
```

## 2. 架构路线：Engine → Adapter → Artifact

> Adapter 职责边界与长期演进策略以 [codegraph-adapter-selection-and-evolution.md](codegraph-adapter-selection-and-evolution.md) 为准
> （Canonical 四模型：Symbol / Relation / Evidence / Resolution）；本节只保留选型视角的快速视图。

```text
本地仓库
   │
   ▼
┌───────────────────────────────────────┐
│ OSS Analysis Engine（默认候选：         │
│ codegraph-ai/CodeGraph；tree-sitter；   │
│ 可选增强：Pyright / astroid）           │
│ —— headless 一次性模式，无 MCP 依赖      │
└──────────────┬────────────────────────┘
               │ 原始解析结果（JSON）
               ▼
┌───────────────────────────────────────┐
│ Canonical Adapter（本仓库）             │
│ 四态判定 + source_span 证据 + 漏斗计数   │
└──────────────┬────────────────────────┘
               ▼
   本仓库 CodeGraph Artifact（schema v2：source_span / resolution / 调用统计）
               │
        validate / enrich（既有 validator + evaluator）
               ▼
        GraphRAG / API / UI
```

边界原则（对应 ADR-001 / ADR-010/011 精神）：

1. **第三方负责"看懂代码"；本仓库负责"统一语义、证据、契约、GraphRAG"。**
2. 引擎原始输出**不直接**作为 Artifact——必须经 Canonical Adapter（四态 + 证据 + 稳定 ID 映射 + 排序去重）。
3. 引擎是**适配器细节**（infrastructure 层），完整解析契约（四态 / span / 统计）才是稳定接口——引擎可替换。
4. 自研 `PythonAstAnalyzer`（DEFINES/IMPORTS）不回退；其能力作为 Gap 兜底与证据补扫（见 §6 ADR v2）。

## 3. 候选优先级（修订版）

采纳 feedback §四的排序框架，逐项以 2026-10-03/04 实测核实：

| 优先级 | 项目 | 用途 | 许可证（实测） | 维护（实测） | 与旧调研的差异 |
| --- | --- | --- | --- | --- | --- |
| **S** | codegraph-ai/CodeGraph | **默认代码结构引擎（POC 首选）**：symbols / imports / calls / graph 遍历 / 入口 | Apache-2.0 | 活跃（pushed 2026-10-02）；solo 维护者；108★、23 fork | **旧调研完全遗漏**（feedback §二指出的最大缺口） |
| **S** | tree-sitter | 底层解析能力（经引擎间接使用；直接接触仅限第二解析器场景） | MIT | 极活跃 | 由"观察项"升为"底层能力" |
| **A** | Pyright | Python 精度增强器（类型推断 / definition resolution） | **MIT**（`LICENSE.txt` 文本实测；GitHub 判 NOASSERTION 系微软自定义头，与 scip-python 同款） | 微软；极活跃（pushed 2026-10-02） | 由未列升级为 L2 增强器 |
| **A** | scip-python | pyright 索引器（若需要 SCIP 索引形态/跨库引用） | MIT（pyright 派生） | 活跃；**Node16+ 运行时代价** | 旧调研 R7"否决"→ 降级为"按需增强器"（保留代价提示） |
| **A** | astroid | Python fallback（inference / instance / MRO） | LGPL-2.1 | 活跃（pushed 2026-09-30） | 由"设触发点"改为"A 级 fallback 候选" |
| **B** | griffe | 借机制或局部使用（import / alias / API symbols） | ISC | 活跃 | 保持不变（局部借鉴） |
| **B** | PyCG | 借算法与 benchmark（CALLS 测试集、解析思路） | Apache-2.0 | 已归档（仅作参考与测试集） | 由"机制借鉴不引依赖"细化为"算法+benchmark 来源" |
| **B** | code2flow | 借 conservative 策略（ambiguous 显式处理） | MIT | 缓慢活跃（2025-07） | 保持不变（策略参考） |
| **C** | JARVIS | 论文参考（flow-sensitive / FTG） | **无许可证**（代码不可用） | 研究原型 | 保持不变 |
| **C** | Joern | **暂不上**（重型 CPG / data-flow / security；feedback 新增候选） | Apache-2.0 | 活跃（pushed 2026-10-03）；3.5k★ | 新增观察项（推迟到安全/数据流需求出现） |
| **D** | pyan3 | 不采用 | GPL-2.0 | 活跃 | 保持不变 |

勘误与说明：

- **codegraph-ai/CodeGraph 实现语言为 Rust**（README 自述"A single Rust binary"，构建命令 `cargo build`）；GitHub 语言统计标记为 C（仓库含 vendored C 组件），引用时以 README/构建方式为准。
- Prigh（Pyright）许可证：与 scip-python 相同的"MIT 文本 + 微软自定义头"文件（`LICENSE.txt`，本日实测 1150 字节）——**这是 MIT**，不是专有许可。
- Joern "暂不上"的理由（采纳 feedback）：CPG/data-flow 属重型栈，与本阶段"快速获得调用关系"的目标不成比例；出现安全/污点分析需求时再评审。

## 4. 首选引擎核实：codegraph-ai/CodeGraph（2026-10-04 实测）

### 4.1 事实清单（每条有据）

| 项 | 实测结果 | 证据 |
| --- | --- | --- |
| 许可证 | Apache-2.0 | GitHub API `license.apache-2.0`；README License 段 |
| 维护状态 | 未归档；pushed 2026-10-02；open issues 3 | GitHub API 快照 |
| 社区规模 | 108★ / 23 fork；README 自述 solo developer | API + README |
| 实现形态 | Rust 单二进制 `codegraph-server`（同时服务 MCP 与 LSP） | README Architecture 段 |
| 解析 | tree-sitter；38 语言（默认社区构建 32 种；Python 在默认集内） | README Languages 段 |
| 图能力 | callers / callees / call graph / dependency graph / traverse / find_entry_points（main·http_handler·cli_command·event_handler·test） | README Tools + tool-calling-guide |
| Python 特化 | HTTP handler 检测覆盖 FastAPI / Flask / Django | README Languages 段 |
| 持久化 | RocksDB（`~/.codegraph/graph.db`）+ FNV-1a 增量索引；重启秒开 | README Architecture 段 |
| **Headless 接入** | **`--graph-only`（跳过 ONNX，10–50× 快）+ `--run-tool <tool> --tool-args '{...}'` 一次性模式（无 MCP 握手，脚本友好）** | README MCP flags + GitHub Action 例 |
| Windows 支持 | **官方发布 `codegraph-server-win32-x64.exe`（v0.20.1，含 `.sha256`）** | GitHub Releases API 实测 |
| 工具面 | 42 个社区工具（graph/analysis/导航全在社区版；pro 主要是安全类） | README Tools 段 |
| 数据形态 | document/occurrence 无关——其 MCP 响应为 JSON；符号以整数 `node_id` + `location{file,line,end_line}` 表示 | tool-calling-guide 响应示例 |

### 4.2 与步骤 5 需求映射（能力 → 缺口 → 处置）

| 步骤 5 需求 | 引擎现状 | 缺口 | 处置 |
| --- | --- | --- | --- |
| 本地函数 / 方法 / 模块属性 / 导入别名调用解析 | 有跨文件 import/call resolution（tree-sitter + 启发式，**精度待 POC 实测**） | 精度未知；DI / decorator 等复杂形态预期弱 | POC 用 Golden 夹具度量；不足时 L2 增强（Pyright/astroid） |
| resolved / ambiguous / dynamic / unresolved 四态 | **无**（工具面未暴露 resolution / confidence 字段；检索 guide 无 `call_site`/`resolved`） | 全部 | **Canonical Adapter 自建**（本仓库差异化价值，feedback §六认同） |
| 调用点行号证据（call-site span） | 文档化响应只见**符号** `location{file,line,end_line}`，无调用表达式行号 | 可能缺失 | **POC 关键验证项**；若确认缺失 → Adapter 用本地 AST 定向补扫（只补证据，不重做解析） |
| 入口识别 | `find_entry_points`（main / http_handler / cli_command / event_handler / test） | 无（是先行件规则的超集） | 与 `analyzers/entry_points.py` 规则对账；表示层设计仍待 ADR |
| 确定性 Artifact | 引擎输出顺序 / 整数 node_id 为其内部实现 | 稳定 ID / 排序 / 双跑字节相等 | Adapter 映射稳定 ID（ADR-010）+ 排序去重 + 既有 validator |
| 离线本地运行 | 本地索引 + 本地 RocksDB；`--graph-only` 无模型下载 | 无 | ✓ |
| Windows 开发机 | 官方 win-x64 二进制 | 无 | ✓（POC 直接用；CI 侧用 linux-x64 资产） |

### 4.3 风险与合规登记

1. **solo 维护者 + 0.x 版本**：升级可能破坏行为。缓解：pin 版本 + 锁二进制 sha256；Apache-2.0 允许必要时 fork 固化（自保底）。
2. **Native binary 供应链**：只用 GitHub Releases 官方资产 + `.sha256` 校验；不使用 IDE 端自动下载机制；引入决策时登记资产哈希。
3. **证据粒度风险**（调用点行号可能缺失）：见 4.2；补扫成本小（我们已有 AST 设施）。
4. **解析语义不透明**：tree-sitter + 启发式，无"为什么这样解析"的契约。缓解：以我们自己的 precision/recall 口径评测引擎（不信任其自述）；四态 Normalizer 兜底。
5. **运行期数据落点**：`~/.codegraph/`（用户目录）。POC 核验是否可重定向；与我们仓库内 Artifact 纪律不冲突（引擎状态≠我们的交付物）。
6. **版本观测差异**：README 提及 0.21 升级路径，但 Releases 最新为 v0.20.1（2026-08-10）——POC 记录实际所用版本与行为差异。
7. **许可证合规**：Apache-2.0 对私有使用无分发义务；若未来随产品分发其二进制/代码，需保留 LICENSE/NOTICE 与变更说明。

## 5. POC Spike 计划（小步、可判定）

### 5.1 目标与通过线

- 目的：回答"引擎当前能力能不能覆盖 70%～90% 的解析需求"（feedback §二）——**用我们自己的夹具与口径度量**。
- 通过线（进入集成设计）：夹具意图命中 **≥ 80%** + call-site 证据可得性结论明确 + 输出 JSON 可解析 + 无崩溃。
- 失败分支：命中明显不足 → 评估 L2（Pyright / astroid 增强）路径；个别缺口 → L4 定向 resolver（如调用点补扫）。

### 5.2 夹具（复用先行件，不新造）

- 主夹具：`eval/codegraph/cases/golden-python-calls/repo`（6 文件），已覆盖 feedback 10 类矩阵中的 7–8 类：
  直接调用 / 模块属性 / 导入别名 / 实例化（构造）/ self 方法 / 局部实例方法 / 高阶回调（ambiguous）/ getattr（dynamic）/ stdlib（unresolved）/ main guard / FastAPI。
- 缺口类别（inheritance / decorator / DI）：POC 阶段在 `eval/codegraph/.outputs/codegraph-ai-poc/probes/`（gitignored）放补充探针，**不改动已入库夹具**；是否并入正式夹具待设计冻结时决定。
- 对照基准：夹具 README 的"初步归属"表（resolved / ambiguous / dynamic / unresolved 意图）。

### 5.3 步骤（每步留痕到 `.outputs/codegraph-ai-poc/`）

1. **获取引擎**：下载 Releases `codegraph-server-win32-x64.exe` + `.sha256`（v0.20.1），校验哈希后放入仓库外目录（建议 `~/.codegraph/bin/`，与官方生态同规；**不入仓**）。
2. **核验 CLI**：`codegraph-server.exe --help`，确认 `--workspace / --graph-only / --run-tool / --tool-args` 实际形态（文档与二进制以二进制为准）。
3. **索引**（graph-only，无 MCP）：`--workspace <夹具 repo> --graph-only --run-tool codegraph_find_entry_points --tool-args '{"entryType":"all","limit":50}'`。
4. **逐工具采样**：`codegraph_symbol_search` / `codegraph_get_callees` / `codegraph_get_callers` / `codegraph_get_call_graph`（`uri` + **0-indexed line**，或 `nodeId` 字符串）/ `codegraph_traverse_graph`（`edgeTypes:[Calls]`）；对夹具每个调用形态取 1–2 个样本。
5. **对照与判定**：按夹具归属表逐项打分（命中 / 偏差 / 缺失），专项检查 **call-site 行号是否出现**。
6. **产出**：`eval/codegraph/.outputs/codegraph-ai-poc/{raw_responses, scorecard.md}`（原始响应 + 记分卡）；结论摘要回填本文 §5.4。

### 5.4 POC 结果（2026-10-04 执行）

| 检查项 | 结果 | 证据文件 |
| --- | --- | --- |
| 夹具意图命中率（≥80%？） | ❌ **未达标**：契约口径 2/6（≈33%，含 1 部分命中）｜宽口径内在调用 4/9（≈44%）；**假阳性 0 观察** | `.outputs/codegraph-ai-poc/scorecard.md` |
| call-site 行号证据 | ❌ **不可得**：`call_site` 字段实为调用者符号 span（`end_column=10000` 哨兵）→ AST 定向补扫确认必要 | `raw/c_callers_*.json` |
| 入口识别对账（先行件规则） | 部分：`main` ✓；**FastAPI web_app 未检出**（夹具无路由）；另 8 条 public_api 噪声 + 1 条 event_handler 误标 | `raw/a_find_entry_points.json` |
| 补充探针（inheritance/decorator/DI） | 未执行（先定方向） | — |
| 实际引擎版本与稳定性 | v0.20.1 win-x64，sha256 通过；36/36 rc=0，one-shot 稳定；数据落点 `C:\Users\dell\.codegraph`（C 盘，未见重定向开关） | `raw/*.meta.txt` |

**POC 结论（2026-10-04）**

- 命中不足（<80%），触发 §5.1 失败分支；缺失集中：① **类方法体内调用全缺**（`run` callees 空，含 `self._format` 与 `greet`）；② **模块属性/别名调用未解析**（`helpers.shout` ×2、`import ... as` 别名）；③ 局部实例方法（原属“待定”）。precision 观察无损（0 假阳性）。
- 已确认：无调用点行号证据 → 调用点补扫为刚需（ADR-012 v2 决策 2 预案成立）。
- 下一步分支（**已决 2026-10-04：A 混合增强**）：Engine 负责跨文件图 / 入口 / 高精度直呼边；**自研 AST 调用补扫器**补齐方法体 / self / 别名盲区 + call-site 行号证据（stdlib AST，零新依赖，复用既有解析设施）；B（Pyright/astroid 第二分析器）与 C（纯 Engine）否决或备选，代价见 scorecard。

## 6. ADR-012 v2 草案：CALLS 获取与归一化纪律（供 Human 审核后落账 `docs/adr/`）

> 与 v1 草案（`codegraph-calls-pre-research.md` §5，"自研解析"语境）的关系：**契约部分（四态 / 调用点证据 / 统计漏斗 / schema v2）保持不变；获取方式改为外部引擎 Adapter 优先**。落账建议文件名 `ADR-012-calls-acquisition-normalization.md`（编号 012 空闲）；POC 结果与 Human 审核后落账。已决口径（2026-10-04，详见 [决策文档 §16](codegraph-adapter-selection-and-evolution.md)）：P1=1-A（扩类仅 Adapter 内部维度）、P7=同一个（Canonical = 域模型演进）。

- 状态：Proposed（草案 v2 · 待 POC 证据与审核）
- 日期：2026-10-04

**Context**

步骤 5 需要为 GraphRAG 提供可信、可追溯的调用关系。调研确认：（a）四态 resolution 与调用点证据无现成协议可借，须自建；（b）Human 修订主要矛盾为"借鉴并使用开源快速落地"，成本最低路径是"OSS 引擎 → Adapter → 本仓库 Artifact"；（c）首选引擎 codegraph-ai/CodeGraph（Apache-2.0、活跃、win 二进制、headless 一次性模式）与步骤 5 需求高度重合，但存在四项缺口：四态、调用点证据、确定性、以及精度未知。若直接采用引擎输出，将破坏 ADR-010/011 契约与 Evidence First 纪律。

**Decision**

1. **获取层（引擎 ≠ 契约）**：CALLS 解析默认经外部引擎（首选 codegraph-ai/CodeGraph，经 POC 验证后定版；备选 L2：Pyright/scip-python/astroid 增强）；引擎以 **headless 一次性模式**（`--run-tool`）接入，不引入 MCP 运行时依赖；引擎位于 infrastructure 层适配器，**引擎可替换**（Canonical Adapter 契约才是稳定接口）。
2. **归一化层（本仓库职责）**：引擎原始输出必须经 Canonical Adapter（含 Resolution Normalizer 职责）——产出四态（resolved / ambiguous / dynamic / unresolved）+ source_span + 漏斗计数 + 稳定 ID 映射（ADR-010）+ 确定性排序去重；引擎未给出调用点行号时，用本地 AST 定向补扫补齐证据（只补证据，不重做解析）。
3. **契约部分（v2 范围，grill 2026-10-04 冻结）**：`CodeEdge` 增可选 `source_span`（calls 必填）与 `resolution`（calls 必填）；**ambiguous 物化 + 防爆护栏**（候选上限 5 / `is_truncated` 标记 / `ScanStats.oversized_ambiguous_calls`）；**CodeGraph 增图级 `entries` 清单**（与 nodes/edges 平级，不入 EdgeKind）；`ScanStats` 增调用漏斗计数；`CodeGraph.schema_version` 1→2；不新增错误码。
4. **引擎准入条件**：Apache-2.0 等宽松许可登记；版本 pin + 二进制 sha256 校验；平台资产（本机 win-x64、CI linux-x64）；离线可运行（`--graph-only`）；**引擎故障/不可用时降级**为既有 AST 能力 + 显式 unresolved 计数（不虚假成功、不静默）。
5. **自研保底**：`PythonAstAnalyzer` 既有 DEFINES/IMPORTS 能力不回退；自研 resolver 仅用于补齐引擎无法覆盖的 gap（L4）。
6. **落地顺序**：POC（§5）→ 通过线与缺口清单 → 集成设计（Canonical Adapter 接口 + 四态判定规则 + Golden 期望冻结）→ 评测 Baseline v2（只用新建不覆盖纪律）→ ADR 落账与架构文档同步。
7. **相关决议（2026-10-04）**：P1=1-A（SymbolKind 扩类仅 Adapter 内部维度，对外保持 3 类）；P7=同一个（Canonical Artifact = `app/domain/codegraph` 域模型演进）；P2–P6 处置建议见 [决策文档 §16](codegraph-adapter-selection-and-evolution.md)。

**Alternatives**

- **纯自研 CALLS resolver**（v1 语境）：可控性与自研比例最高，但成本高、落地慢，与主要矛盾冲突；保留为 L4 兜底与降级路径，不作为默认。
- **引擎输出直用（不归一化）**：最快但放弃四态 / 证据 / 确定性契约，违反完成门槛"不把动态推测伪装成确定调用关系"；否决。
- **双引擎并行默认**（引擎 + Pyright 同时跑）：精度上限最高，但复杂度与运行成本翻倍；改为"按 POC 缺口触发增强"。
- **引入 SCIP/Protobuf 作为中间格式**：与 JSON Artifact 真源重复；否决（保持 JSON 归一化）。

**Consequences**

- 正向：步骤 5 落地速度大幅提升；Evidence First（调用点行号、四态、统计）纪律不外包；引擎可替换、契约稳定；既有领域契约仅做一次受控升级（schema v2）。
- 负向：引入外部 native 依赖与供应链风险（solo/0.x，已列缓解）；解析精度受引擎启发式上限约束，需持续用自有 Golden 度量；调用点证据可能需补扫（额外一次 AST 遍历）；`~/.codegraph` 运行期状态需在运维文档登记。
- 复审触发：引擎不再活跃或行为回归、Golden 命中率跌破通过线、许可证变化、需要多语言解析（复用引擎 38 语言能力时另行评审）、或引入第二解析器改变能力上限。

## 7. 决策点与后续同步

**待 Human 决策（本次）**

1. 本选型文档（`docs/codegraph/codegraph-oss-adoption.md`）：**已认可**（2026-10-04，按方案 B 推进）；
2. **POC 执行方式**：已决（grill Q1）——Human 手动下载（sha256 校验、存仓库外），Agent 校验并执行 POC 与记分；**POC 已执行**（§5.4：命中未达标 → 已决混合增强 A）；
3. **ADR-012 v2 落账时机（改述）**：由“POC 通过后”改为“**集成设计冻结后**”（ADR 含方案 B 混合增强架构与契约 v2）；契约变更实施同批推进。

**POC 通过后的文档同步清单（预告，非本次执行）**

- `architecture.md`：状态表 + 演进顺序（Phase 2D"CALLS"改为"外部引擎 Adapter 接入"叙事）；
- `CLAUDE.md`：§五状态地图 + 模块速查（新增引擎适配器模块后）；
- `eval/codegraph`：`golden-python-calls` 期望冻结 + Baseline v2；
- dev-log 与本地记忆按惯例登记。
