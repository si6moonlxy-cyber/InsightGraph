# Adapter 契约影响分析（P1–P6）与命名结构决议（P7/P9）

> 状态：决策输入（POC 与 ADR-012 v2 直接可用）｜日期：2026-10-04
> 依据：[决策文档](codegraph-adapter-selection-and-evolution.md)（架构真源）、[选型与 POC 计划](codegraph-oss-adoption.md)、审阅问题单 P1–P12
> 口径：与冻结契约（[ADR-010](../adr/ADR-010-codegraph-contract-discipline.md) / [ADR-011](../adr/ADR-011-scan-result-contract.md)）的差量逐项定责；
> 「已决」= Human 2026-10-04 决定，「建议」= 待 POC/ADR 时点确认。

## 1. 契约差量分析（P1–P6）

| #                    | 差量                                                                             | 现契约                                                          | 文档诉求                                                                  | 影响面                                                                                                                                   | 处置  |
| -------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------ | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | --- |
| **P1** | SymbolKind 闭集 | `NodeKind = {module, class, function}`；方法 = function + `Class.method`（步骤 4 口径） | +METHOD / VARIABLE / INTERFACE / TYPE / PARAMETER / UNKNOWN | kinds.py、validator、Golden/evaluator、CLAUDE.md §二、architecture.md §5.1 | ✅ **已决 1-A**：扩类**不进入对外契约**——仅作 Adapter 内部维度；对外保持 3 类；未来如需对外扩类 → 单独立 ADR（走 schema_version 流程） |
| **P2** | SourceSpan | `file_path + line_start + line_end`；节点必填、边无 | +`start_col/end_col`；symbol span 与 callsite span 区分 | SourceSpan 模型与校验、content_hash 口径、边证据 | 建议：**callsite span 进 v2**（`CodeEdge.source_span`，calls 必填——承接既有提案）；**列号 v1 不承诺**（声明"可选、以引擎实际能力为准"；引擎响应现仅 file/line/end_line，POC 验证后定） |
| **P3** | EdgeKind 闭集 | `{defines, imports, calls}` | +CONTAINS / INHERITS / IMPLEMENTS / REFERENCES / ENTRY_POINT | kinds.py、validator、evaluator、文档 3 处同步 | 建议**分批**：v2 首批候选 = **ENTRY_POINT + CONTAINS**（前者先行件已识别、表示层随 ADR 定；后者定义树可得）；v2.x = INHERITS / IMPLEMENTS；REFERENCES 最后。每批 = 一次受控升级 |
| **P4** | 身份格式 | ADR-010 `{repository_id}:{kind}:{qualified_name}` | 示例 `symbol://python/...` 与 `python:function:...` 并存 | 全部 ID 构造与跨层引用（GraphRAG / datamodel 依赖稳定 ID） | 建议：**canonical ID 沿用 ADR-010**；文档两示例收敛为一个并标注"示意，以 ADR-010 为准"；`upstream_node_id` 只存在于 Adapter 映射，不进入 Artifact |
| **P5** | Evidence 粒度 | 边无 provenance 字段 | 逐边 `EdgeEvidence(provider/version/node_id/method)` | CodeEdge 字段、Artifact 体积、多后端融合 | 建议：**v2 = 扫描级 provenance**（图根 / ScanResult 元数据：provider、version、query 方法集合、资产哈希）；多后端 Evidence Fusion 启动时再逐边化（届时再升级） |
| **P6** | 状态枚举 | `resolution ∈ {resolved, ambiguous}`（v2 提案） | "conflict" 第五态（文档留待后议） | 枚举闭集纪律、evaluator | 建议：**v1 不引入**；写入 ADR 复审触发（多后端融合时评审） |

## 2. 与升级节奏的耦合

- **schema_version 1→2 一次承载**：P2（callsite span）+ resolution 字段 + 调用漏斗统计（ADR-012 v1 既有提案）；（可选）P3 首批 ENTRY_POINT/CONTAINS 是否并入，由 ADR 决定。
- **Golden 策略**：调用相关期望用**新 fixture 增量**（不改旧 expected）；Baseline v2 新建不覆盖 v1（既有纪律）。
- **validator 增量**：域校验器增"calls 边必备 `source_span + resolution`"不变量；`eval/codegraph/validate.py` 同步。
- **文档同步位点**（契约变更实施时）：`kinds.py`、`models.py`、CLAUDE.md §二、`architecture.md` §5.1、ADR-010 §4、eval/evaluator。

## 3. 命名与结构决议（P7/P9 调整后）

**P7 已决「同一个」**：Canonical Artifact = **既有 `app/domain/codegraph` 域模型的演进**（单域模型；Adapter 直接构造/映射到它，不建平行 domain 层，不设第二套 artifact 定义）。

调整后的目录结构（取代决策文档 §7 草图中的 `domain/` 子层）：

```text
backend/app/infrastructure/code_intelligence/
├── providers/
│   └── codegraph_ai.py     # 引擎调用（headless --run-tool；引擎可替换）
├── raw_models/             # 引擎原始响应 DTO（provider 私有，不进域层）
└── adapter/                # Canonical Adapter（映射 + 归一化）
    ├── identity.py         # upstream node_id → ADR-010 稳定 ID（P4）
    ├── symbol_mapper.py    # 引擎 kind → 对外 3 类（1-A：扩类仅内部维度）
    ├── relation_mapper.py  # 引擎 edge → EdgeKind（P3 分批白名单）
    ├── span_mapper.py      # 0/1-based、inclusive/half-open → SourceSpan（P2）
    ├── resolution.py       # 四态分类（原 "Resolution Normalizer" 职责）
    ├── provenance.py       # 扫描级 provenance（P5）
    └── canonicalize.py     # 排序 / 去重 → 域模型构造（确定性纪律）
```

- 不设独立 `validation/`：复用 `app/domain` Pydantic 校验器 + `eval/codegraph/validate.py` 不变量——「7-同一个」的直接收益。
- 依赖方向：infrastructure → domain（既有架构测试自动约束，无需新增守卫）。

**P9 命名收敛**：「**Canonical Adapter**」为统一术语；「Resolution Normalizer」降级为其内部组件名（`adapter/resolution.py`）。已同步 [codegraph-oss-adoption.md](codegraph-oss-adoption.md)（§2 图与边界原则、§6 草案措辞）。

## 4. 决策状态

| 项 | 状态 |
| --- | --- |
| P1 = 1-A（扩类仅 Adapter 内部维度） | ✅ 已决（2026-10-04） |
| P7 = 同一个（Canonical = 域模型演进） | ✅ 已决（2026-10-04） |
| P2 列号策略 / P3 首批边型 / P4 收敛表述 / P5 provenance 粒度 / P6 不引入 conflict | ⏳ 建议（POC 与 ADR-012 v2 落账时点确认） |

> 本文是 POC 执行与 ADR-012 v2 的决策输入；POC 通过后按此更新决策文档相应小节，并入 ADR 正式稿。
