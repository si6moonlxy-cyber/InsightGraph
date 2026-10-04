# CodeGraph Adapter 选型与长期演进决策

> 状态：架构调研结论  
> 目标：明确 `codegraph-ai/CodeGraph → Adapter → Canonical CodeGraph Artifact → GraphRAG` 路线下，Adapter 的职责边界，以及未来是否需要逐步替换第三方 CodeGraph。  
> 适用阶段：MVP / CodeGraph 解析能力建设前期  
> 核心原则：**第三方 CodeGraph 可替换，Canonical Artifact 不可被第三方实现细节绑死。**
> 更新（2026-10-04）：契约差量与决策记录见 §16；§7 目录已按「Canonical = 现有域模型演进」调整。

---

## 1. 当前结论

当前项目不应优先投入大量时间自研完整代码解析引擎，而应采用：

```text
codegraph-ai/CodeGraph
        ↓
Canonical Adapter
        ↓
Your CodeGraph JSON Artifact
        ↓
GraphRAG / Evidence / API / UI
```

当前开发的核心难题已经不是“怎么解析代码”，而是：

> **Canonical Adapter Contract 怎么定义。**

它必须满足两个目标：

1. 充分利用第三方 CodeGraph 已有的解析、索引、调用关系和图遍历能力；
2. 不让上层 GraphRAG、API、UI 与 `codegraph-ai/CodeGraph` 的内部结构形成强耦合。

因此，项目真正应该长期拥有的是：

```text
Canonical Symbol Model
Canonical Relation Model
Canonical Evidence Model
Canonical Resolution Semantics
```

而不是现阶段就必须拥有完整 Parser / Resolver / Indexer。

---

## 2. Adapter 不是简单 DTO 转换器

Adapter 不应该只是：

```text
CodeGraph JSON
    ↓
字段改名
    ↓
Your JSON
```

它更适合作为第三方代码分析引擎和内部领域模型之间的 **Anti-Corruption Layer / Canonicalization Layer**。

建议职责如下：

```text
codegraph-ai/CodeGraph
        │
        ▼
Raw Provider Result
        │
        ├── Identity Normalization
        ├── Symbol Normalization
        ├── Path Normalization
        ├── SourceSpan Normalization
        ├── Relation Normalization
        ├── Resolution Classification
        ├── Evidence / Provenance
        └── Deterministic Canonicalization
        │
        ▼
Canonical CodeGraph Artifact
```

---

## 3. Adapter 必须解决的核心问题

### 3.1 稳定节点身份

第三方 CodeGraph 的内部 `node_id` 不应成为项目长期 Artifact 的唯一身份。

推荐构造自己的稳定 ID，例如：

```text
python:function:backend/app/services/user.py:UserService.create_user
```

或者：

```text
symbol://python/backend.app.services.user/UserService#create_user()
```

> 2026-10-04 已决：canonical ID 沿用 ADR-010 格式 `{repository_id}:{kind}:{qualified_name}`；上述示例仅作示意。

目标是做到：

```text
upstream_node_id
        ↓
canonical_symbol_id
```

这样即使未来：

- CodeGraph 升级；
- 第三方重新索引；
- 切换到 Pyright / SCIP；
- 自研 Resolver；

上层 Artifact 身份体系仍可保持稳定。

---

### 3.2 SymbolKind 规范化

建议内部维护自己的闭集：

```text
MODULE
CLASS
FUNCTION
METHOD
VARIABLE
INTERFACE
TYPE
PARAMETER
UNKNOWN
```

> 2026-10-04 已决（1-A）：扩类不进入对外契约，仅作 Adapter 内部维度；对外保持 module / class / function（方法 = function + `Class.method`）。

Adapter 负责将上游类型映射到内部类型。

例如：

```text
CodeGraph Function → FUNCTION
CodeGraph Method   → METHOD
CodeGraph Class    → CLASS
```

GraphRAG 不应直接依赖第三方的 enum。

---

### 3.3 SourceSpan 规范化

内部需要统一：

```text
path
start_line
start_col
end_line
end_col
```

并明确：

- 0-based / 1-based；
- inclusive / half-open；
- 路径是否 repo-relative；
- Windows / Unix path 是否归一；
- symbol span 与 callsite span 是否区分。

建议所有第三方坐标统一转换后再进入 Artifact。

---

### 3.4 Relation 规范化

建议内部关系模型至少覆盖：

```text
DEFINES
CONTAINS
IMPORTS
CALLS
INHERITS
IMPLEMENTS
REFERENCES
ENTRY_POINT
```

第三方关系名称不直接向上暴露。

未来无论输入来自：

```text
CodeGraph
Pyright
SCIP
Astroid
Custom Analyzer
```

最终都映射成统一 Relation。

---

## 4. Resolution Semantics 应由项目自己拥有

建议保留四态：

```text
resolved
ambiguous
dynamic
unresolved
```

含义：

### resolved

唯一、明确、可回溯的目标。

例如：

```text
A.foo()
→ repo 内唯一确定的方法定义
```

### ambiguous

一个调用点存在多个合理候选。

例如：

```text
A → B
A → C
```

且静态信息不足以确认唯一目标。

### dynamic

目标由运行期决定。

例如：

```text
getattr(...)
reflection
callback registry
runtime monkey patch
dynamic import
```

### unresolved

存在调用事实，但无法定位到仓库内目标。

例如：

```text
stdlib
third-party package
missing source
unknown symbol
```

Adapter 的责任不是重新实现完整静态分析，而是：

> **将上游解析结果规范化为项目自己的可信状态。**

---

## 5. Evidence / Provenance 应作为一等数据

建议 Canonical Artifact 记录第三方解析来源。

例如：

```python
EdgeEvidence(
    provider="codegraph-ai",
    provider_version="...",
    provider_node_id="1549",
    method="get_callees",
)
```

最终：

```python
CodeEdge(
    kind="CALLS",
    source_id="...",
    target_id="...",
    resolution="resolved",
    source_span=...,
    evidence=...
)
```

这样未来可以支持多解析器交叉验证。

例如：

```text
CodeGraph → A → B
Pyright   → A → B
```

可以提高可信度。

而：

```text
CodeGraph → A → B
Pyright   → A → C
```

则可以进入：

```text
ambiguous
```

或者：

```text
conflict
```

后续再决定是否增加独立冲突状态。

因此 Adapter 可以逐渐演进成：

> **Code Intelligence Evidence Fusion Layer**

但 MVP 阶段不需要一次性实现完整多后端融合。

---

## 6. Provider 与 Adapter 应分离

建议不要让 Canonical Adapter 直接绑定 `codegraph-ai/CodeGraph`。

可以保持一层很薄的 Provider：

```python
class CodeIntelligenceProvider(Protocol):
    async def symbols(self): ...
    async def relations(self): ...
    async def callers(self, symbol): ...
    async def callees(self, symbol): ...
    async def entry_points(self): ...
```

当前实现：

```text
CodeGraphAIProvider
        ↓
CanonicalAdapter
        ↓
CodeGraphArtifact
```

未来可以增加：

```text
PyrightProvider
SCIPProvider
AstroidProvider
CustomAnalyzerProvider
```

这里的重点是：

> Provider 抽象的是“外部代码分析能力”，不是提前抽象整个 Parser。

因此不需要现在设计复杂 Parser Wrapper。

---

## 7. 推荐的当前架构

```text
GitHub Repo / Local Repo
        │
        ▼
┌─────────────────────────────┐
│ codegraph-ai / CodeGraph    │
│                             │
│ Parser                      │
│ Symbol Resolver             │
│ Call Resolver               │
│ Graph Engine                │
│ Index                       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ CodeGraphAIProvider         │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Canonical Adapter           │
│                             │
│ identity                    │
│ symbol mapper               │
│ relation mapper             │
│ source span                 │
│ resolution                  │
│ evidence                    │
│ canonicalization            │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Canonical CodeGraph Artifact│
└──────────────┬──────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
     GraphRAG       API / UI
```

推荐目录（2026-10-04 调整版：「Canonical = 现有域模型演进」——不设独立 `domain/` 与 `validation/` 子层，复用 `app/domain` 校验器与 `eval/codegraph` 不变量校验）：

```text
backend/app/infrastructure/code_intelligence/

providers/
    codegraph_ai.py          # 引擎调用（headless --run-tool；引擎可替换）

raw_models/                  # 引擎原始响应 DTO（provider 私有，不进域层）
    symbol.py
    relation.py

adapter/                     # Canonical Adapter（映射 + 归一化）
    identity.py              # upstream node_id → ADR-010 稳定 ID
    symbol_mapper.py         # 引擎 kind → 对外 3 类（1-A：扩类仅内部维度）
    relation_mapper.py       # 引擎 edge → EdgeKind（分批白名单）
    span_mapper.py           # 0/1-based、inclusive/half-open → SourceSpan
    resolution.py            # 四态分类（原 “Resolution Normalizer” 职责）
    provenance.py            # 扫描级 provenance
    canonicalize.py          # 排序 / 去重 → 域模型构造
```

---

## 8. 当前最推荐的选型方案

### 方案 A：直接转换

```text
CodeGraph API
    ↓
Pydantic Model
```

优点：

- 开发最快；
- 适合验证 Spike。

缺点：

- 高耦合；
- 第三方 schema 改动会向上传播；
- 未来切换引擎成本高。

结论：

> 仅适合一次性 Spike，不建议作为正式架构。

---

### 方案 B：Provider + Canonical Adapter

```text
CodeGraph Provider
        ↓
Canonical Adapter
        ↓
Canonical Artifact
```

优点：

- 当前开发量仍然较低；
- 第三方实现细节被隔离；
- Artifact 稳定；
- 支持未来局部替换；
- 可以增加第二分析器。

结论：

> **当前正式开发推荐方案。**

---

### 方案 C：多 Backend + Evidence Fusion

```text
CodeGraph
Pyright
SCIP
Astroid
Custom Resolver
    ↓
Evidence Fusion
    ↓
Canonical Artifact
```

优点：

- 精度上限高；
- 可以做冲突检测；
- 可以形成产品核心能力。

缺点：

- 实现复杂；
- 评测成本高；
- MVP 阶段容易过度设计。

结论：

> 暂不实施，但架构应允许未来演进到此方案。

---

## 9. 未来是否需要拆掉第三方 CodeGraph

结论：

> **未来可能需要局部替换，但不应该现在就以“最终必须全部自研”为目标。**

更合理的策略是：

```text
Use
    ↓
Measure
    ↓
Find Gap
    ↓
Enrich
    ↓
Replace Weak Subsystem
```

而不是：

```text
Use
    ↓
Fork
    ↓
Rewrite Everything
```

---

## 10. 最可能的未来演进路径

### Phase 1：直接使用 CodeGraph

```text
CodeGraph
    ↓
Adapter
    ↓
Artifact
```

目标：

- MVP；
- 验证代码结构与 GraphRAG 链路；
- 建立 Golden Cases；
- 获取真实精度和性能数据。

---

### Phase 2：增加 Targeted Enricher

例如：

```text
CodeGraph
    +
PythonEnricher
    +
Pyright / Astroid
        ↓
Adapter
```

只补 CodeGraph 明显不足的场景：

- Python instance method；
- inheritance / MRO；
- dependency injection；
- decorator；
- callback；
- framework magic。

这是预计性价比最高的阶段。

---

### Phase 3：局部替换 Resolver

如果 Call Resolution 成为明显瓶颈：

```text
CodeGraph
├── parser
├── graph
└── index

Your Resolver
        ↓
Canonical Artifact
```

此时仍可以保留 CodeGraph 的：

- tree-sitter；
- indexing；
- storage；
- graph traversal。

只替换最弱的一层。

---

### Phase 4：自主 Code Intelligence Engine

只有出现明确 ROI 时，再考虑：

```text
tree-sitter
    ↓
Own Symbol Model
    ↓
Own Resolver
    ↓
Own Graph Builder
    ↓
Own Index
    ↓
Canonical Artifact
```

这应该被视为产品成熟阶段的战略选择，而不是 MVP 的工程前提。

---

## 11. 什么时候应该开始自研 / 替换

只有第三方开始出现以下问题时才应该评估替换。

### 11.1 精度瓶颈

例如：

```text
Python method resolution
dynamic dispatch
framework magic
```

持续影响 GraphRAG 答案正确率。

---

### 11.2 信息缺失

第三方只返回：

```text
A → B
```

但产品需要：

```text
callsite
candidate set
resolution evidence
reason
source span
```

且无法从上游获得。

---

### 11.3 性能瓶颈

例如：

- monorepo 索引时间过长；
- 内存不可接受；
- 增量更新不足；
- 查询延迟无法满足产品目标。

---

### 11.4 语言语义瓶颈

tree-sitter 可以解析语法，但无法提供项目所需的：

```text
type inference
generic resolution
runtime binding approximation
framework semantics
```

---

### 11.5 产品差异化

当产品核心竞争力开始变成：

> “我们能比通用代码图工具更准确地还原代码真实调用链和实现证据。”

此时 Resolver / Code Intelligence Engine 已经变成核心 IP，才值得收回。

---

## 12. 现在不应该做的事情

当前阶段不建议：

```text
1. Fork CodeGraph 后立刻长期维护
2. 重写 tree-sitter parsing
3. 自研完整跨语言 Resolver
4. 同时接入 4～5 个静态分析引擎
5. 提前设计复杂 Parser Plugin Framework
6. 让 GraphRAG 直接消费 CodeGraph MCP JSON
7. 使用第三方 node_id 作为长期 Symbol ID
```

这些都会把 MVP 从：

```text
产品验证问题
```

变成：

```text
静态分析基础设施项目
```

---

## 13. 当前应该自己拥有的资产

项目现在最应该投入设计质量的是下面四个模型：

### 13.1 Canonical Symbol Model

描述：

```text
代码里“是什么”
```

例如：

```text
module
class
function
method
variable
```

---

### 13.2 Canonical Relation Model

描述：

```text
代码元素“是什么关系”
```

例如：

```text
contains
defines
imports
calls
inherits
references
```

---

### 13.3 Canonical Evidence Model

描述：

```text
“为什么认为这个关系成立”
```

包括：

```text
provider
source span
provider version
query method
raw reference
```

---

### 13.4 Canonical Resolution Semantics

描述：

```text
“我们有多确定”
```

至少：

```text
resolved
ambiguous
dynamic
unresolved
```

这四部分才是长期真正属于项目的 Code Intelligence Domain Model。

---

## 14. 建议的决策原则

未来对于任何第三方解析能力，统一使用以下判断：

```text
第三方负责：
- syntax parsing
- indexing
- basic resolution
- graph construction

项目负责：
- canonical semantics
- evidence
- resolution state
- validation
- deterministic artifact
- GraphRAG consumption
```

原则：

> **租用解析能力，拥有语义契约。**

---

## 15. 最终建议

当前推荐正式路线：

```text
codegraph-ai/CodeGraph
        ↓
CodeGraphAIProvider
        ↓
Canonical Adapter
        ↓
Canonical CodeGraph JSON Artifact
        ↓
Validator
        ↓
GraphRAG
```

短期：

> 不 fork，不重写，不做完整静态分析器。

中期：

> 使用 Golden Cases 找 CodeGraph 的真实 gap，并增加 targeted enricher。

长期：

> 只有当某一子系统成为准确率、性能或产品差异化瓶颈时，才逐层替换。

最终架构目标不是：

> “不依赖第三方 CodeGraph。”

而应该是：

> **“即使明天替换掉第三方 CodeGraph，上层 Canonical Artifact、GraphRAG、API 和 UI 仍然不需要重构。”**

这才是当前 Adapter 设计最重要的成功标准。

---

## 16. 契约差量与决策记录（2026-10-04）

> 来源：契约影响分析（P1–P6，2026-10-04）＋与冻结契约 ADR-010 / ADR-011 的差量定责；
> 「已决」= Human 决定，「建议」= 待 POC / ADR-012 落账时点确认。

| # | 差量 | 现契约 | 本文档诉求 | 影响面 | 处置 |
| --- | --- | --- | --- | --- | --- |
| **P1** | SymbolKind 闭集 | `NodeKind = {module, class, function}`；方法 = function + `Class.method`（步骤 4 口径） | +METHOD / VARIABLE / INTERFACE / TYPE / PARAMETER / UNKNOWN | kinds.py、validator、Golden/evaluator、CLAUDE.md §二、architecture.md §5.1 | ✅ **已决 1-A**：扩类**不进入对外契约**——仅作 Adapter 内部维度；对外保持 3 类；未来如需对外扩类 → 单独立 ADR（走 schema_version 流程） |
| **P2** | SourceSpan | `file_path + line_start + line_end`；节点必填、边无 | +`start_col/end_col`；symbol span 与 callsite span 区分 | SourceSpan 模型与校验、content_hash 口径、边证据 | 建议：**callsite span 进 v2**（`CodeEdge.source_span`，calls 必填——承接既有提案）；**列号 v1 不承诺**（声明“可选、以引擎实际能力为准”；引擎响应现仅 file/line/end_line，POC 验证后定） |
| **P3** | EdgeKind 闭集 | `{defines, imports, calls}` | +CONTAINS / INHERITS / IMPLEMENTS / REFERENCES / ENTRY_POINT | kinds.py、validator、evaluator、文档 3 处同步 | 建议**分批**：v2 首批候选 = **ENTRY_POINT + CONTAINS**（前者先行件已识别、表示层随 ADR 定；后者定义树可得）；v2.x = INHERITS / IMPLEMENTS；REFERENCES 最后。每批 = 一次受控升级 |
| **P4** | 身份格式 | ADR-010 `{repository_id}:{kind}:{qualified_name}` | 示例 `symbol://python/...` 与 `python:function:...` 并存 | 全部 ID 构造与跨层引用（GraphRAG / datamodel 依赖稳定 ID） | 建议：**canonical ID 沿用 ADR-010**（§3.1 已加注）；文档两示例收敛为一个并标注“示意，以 ADR-010 为准”；`upstream_node_id` 只存在于 Adapter 映射，不进入 Artifact |
| **P5** | Evidence 粒度 | 边无 provenance 字段 | 逐边 `EdgeEvidence(provider/version/node_id/method)` | CodeEdge 字段、Artifact 体积、多后端融合 | 建议：**v2 = 扫描级 provenance**（图根 / ScanResult 元数据：provider、version、query 方法集合、资产哈希）；多后端 Evidence Fusion 启动时再逐边化（届时再升级） |
| **P6** | 状态枚举 | `resolution ∈ {resolved, ambiguous}`（v2 提案） | “conflict” 第五态（文档留待后议） | 枚举闭集纪律、evaluator | 建议：**v1 不引入**；写入 ADR 复审触发（多后端融合时评审） |

**升级节奏耦合**

- `schema_version` 1→2 一次承载：P2（callsite span）+ resolution 字段 + 调用漏斗统计（ADR-012 v1 既有提案）；（可选）P3 首批 ENTRY_POINT/CONTAINS 是否并入由 ADR 决定。
- Golden 策略：调用相关期望用**新 fixture 增量**（不改旧 expected）；Baseline v2 新建不覆盖 v1。
- validator 增量：域校验器增“calls 边必备 `source_span + resolution`”不变量；`eval/codegraph/validate.py` 同步。
- 契约实施时的文档同步位点：`kinds.py`、`models.py`、CLAUDE.md §二、`architecture.md` §5.1、ADR-010 §4、eval/evaluator。

**命名与结构决议**

- ✅ P7 已决「同一个」：Canonical Artifact = 既有 `app/domain/codegraph` 域模型的演进（单域模型）；§7 目录已按调整版更新，不设独立 `domain/` 与 `validation/` 子层。
- ✅ P9 命名收敛：「Canonical Adapter」为统一术语；「Resolution Normalizer」降级为其内部组件名（`adapter/resolution.py`）。

**决策状态**

| 项 | 状态 |
| --- | --- |
| P1 = 1-A（扩类仅 Adapter 内部维度） | ✅ 已决（2026-10-04） |
| P7 = 同一个（Canonical = 域模型演进） | ✅ 已决（2026-10-04） |
| P2 列号策略 / P3 首批边型 / P4 收敛表述 / P5 provenance 粒度 / P6 不引入 conflict | ⏳ 建议（POC 与 ADR-012 v2 落账时点确认） |

> 本记录随 §3–§5 一并作为 POC 与 ADR-012 v2 的决策输入；POC 通过后并入 ADR 正式稿。
