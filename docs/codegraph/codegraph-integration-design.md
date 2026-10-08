# CodeGraph 集成设计（步骤 5 · 实施冻结件）

> 状态：**已评审冻结**（sixmoon，2026-10-08；初稿 2026-10-07）。
> 输入与依据：[决策文档](codegraph-adapter-selection-and-evolution.md)（§3–§5 契约与四态、§7 目录、§8 方案 B、§10 Phase 演进、§16 全部已决项）、
> [选型与调研真源](codegraph-oss-adoption.md)（§5 POC、§5.4 结果、§6 ADR-012 决策基线、§8 候选证据与采用边界）、
> POC 记分卡（`eval/codegraph/.outputs/codegraph-ai-poc/scorecard.md`，本地证据）。
> 范围：方案 B「混合增强 A」的落地设计四件套——① Adapter 接口 ② 四态判定表 ③ AST 调用补扫器 ④ schema v2 变更清单；
> 不含：GraphRAG、持久化、API、前端。评审通过后本设计作为 ADR-012 v2（`docs/adr/`）主体并入。

---

## 0. 总览

### 0.1 数据流（实施态）

```text
SourceManifest（步骤 3） ──► PythonAstAnalyzer（步骤 4 基础图：nodes + DEFINES/IMPORTS）
                                    │
                                    ▼
                    ┌───────────────────────────────────────┐
                    │ CallEnrichment（本次新增，M1+M2）        │
                    │                                        │
                    │  ① CallScanner（stdlib AST，M1）        │
                    │     └─ CallFact[]（含 call-site span）  │
                    │  ② EngineProvider（codegraph-ai，M2）   │
                    │     └─ raw DTO ─► Canonical Adapter     │
                    │          ├ identity / symbol / relation │
                    │          ├ span / resolution / provenance│
                    │          └ canonicalize（排序/去重/合并）│
                    │  ③ Merge（engine ∪ scanner，§1.7）      │
                    └───────────────┬───────────────────────┘
                                    ▼
              CodeGraph v2（+CALLS 边 / +entries 清单 / +provenance / schema_version=2）
                                    │
                        validate（域校验器 + eval/validate.py）
                                    ▼
                    evaluator / Baseline v2 / GraphRAG（后续步骤）
```

### 0.2 新增/变更组件清单

| 路径                                                                                                                                                | 类型  | 职责                                                                                                           | 里程碑   |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ------------------------------------------------------------------------------------------------------------ | ----- |
| `backend/app/infrastructure/code_intelligence/pipeline.py`                                                                                        | 新增  | `CallEnrichment` 编排：scanner → engine（可选）→ adapter → merge 产出增强结果与漏斗                                          | M1/M2 |
| `backend/app/infrastructure/code_intelligence/scanner/call_scanner.py`                                                                            | 新增  | stdlib AST 调用点采集与四态分类（§2/§3）                                                                                 | M1    |
| `backend/app/infrastructure/code_intelligence/scanner/binding.py`                                                                                 | 新增  | 模块/类/函数作用域绑定模型（import 形态、self、局部浅推断，§3.2）                                                                    | M1    |
| `backend/app/infrastructure/code_intelligence/providers/engine_port.py`                                                                           | 新增  | `CallGraphProvider` 内部 Protocol（§1.2）                                                                        | M2    |
| `backend/app/infrastructure/code_intelligence/providers/codegraph_ai.py`                                                                          | 新增  | codegraph-ai/CodeGraph subprocess 实现（§1.3）                                                                   | M2    |
| `backend/app/infrastructure/code_intelligence/raw_models/symbol.py` / `relation.py`                                                               | 新增  | 引擎响应 DTO（`extra="ignore"`，§1.4）                                                                              | M2    |
| `backend/app/infrastructure/code_intelligence/adapter/{identity,symbol_mapper,relation_mapper,span_mapper,resolution,provenance,canonicalize}.py` | 新增  | Canonical Adapter 七组件（§1.5）                                                                                  | M2    |
| `backend/app/domain/codegraph/kinds.py`                                                                                                           | 变更  | +`CallResolution`、+`EntryKind`；CALLS 注释更新（§4.1）                                                              | M1    |
| `backend/app/domain/codegraph/models.py`                                                                                                          | 变更  | CodeEdge +3 字段与校验；+`EntryPoint`/`ProviderRecord`；CodeGraph +`entries`/`provenance`；schema_version 语义=2（§4.2） | M1    |
| `backend/app/application/scans/models.py`                                                                                                         | 变更  | +`CallFunnel`；AnalyzeOutcome +`call_funnel`；ScanStats +3 计数（§4.3）                                            | M1    |
| `backend/app/application/scans/service.py`                                                                                                        | 变更  | `_build_stats` 合并漏斗计数（§4.3）                                                                                  | M1    |
| `backend/app/infrastructure/analyzers/python_ast.py`                                                                                              | 变更  | 产出符号表并调用 CallEnrichment；`PARSER_VERSION` → `python-ast/0.2`（§3.1）                                            | M1    |
| `backend/app/infrastructure/analyzers/entry_points.py`                                                                                            | 变更  | 枚举与 `EntryKind` 统一（domain）；捕获语句级 span（行为不变，§4.2）                                                             | M1    |
| `backend/app/foundation/config.py`                                                                                                                | 变更  | +`codegraph_engine_*` 三配置（§1.9）                                                                              | M2    |
| `eval/codegraph/validate.py`                                                                                                                      | 变更  | +calls 证据不变量、+entries 引用不变量（§4.4）                                                                            | M1    |
| `eval/codegraph/evaluator.py`                                                                                                                     | 变更  | 语义比对纳入 CALLS（含 resolution）与 entries；指标扩展（§4.6）                                                               | M1    |

---

## 1. Canonical Adapter 接口设计

### 1.1 分层与归属

- **调用方**：`PythonAstAnalyzer`（infrastructure）在基础图完成后调用 `CallEnrichment.enrich(...)`；**application 端口（`CodeAnalyzer.analyze`）签名不变**（唯一 application 变更 = `AnalyzeOutcome.call_funnel` 与 ScanStats 字段，见 §4.3）。
- **层内边界**：`code_intelligence` 属 infrastructure；不得被 domain / application 直接依赖；引擎细节（二进制、CLI、JSON 形状）只出现在 `providers/` + `raw_models/`。
- **引擎可替换**：上层只见 `CallGraphProvider` Protocol 与 canonical 结果；替换引擎 = 新 provider + 映射，其余不变（Phase 3/4 演进接口）。

### 1.2 Provider 端口（引擎侧，内部 Protocol）

```python
class CallGraphProvider(Protocol):
    name: str                 # 例如 "codegraph-ai/CodeGraph"
    version: str              # 引擎版本（--info 探测，M2 实测确认格式）
    asset_hash: str | None    # 引擎二进制 sha256（可核验时）

    def probe(self, root: Path) -> ProviderStatus: ...
    def calls_for_symbol(self, root: Path, file_rel: str, line_1based: int) -> list[RawCallEdge]: ...
```

- `probe`：启动前探测（二进制存在/可执行/`--info` 成功）→ `available / unavailable(reason)`；不可用只影响降级，不产生错误码（§1.8）。
- `calls_for_symbol`：对单个可调用符号（某文件某行）取**出边**（该符号调用了谁）。POC 实测 `get_call_graph`（uri + line + depth=1）一次调用即可返回 `edges[{from,to,type}]` 与两端节点定位——优于 symbol_search + callers/callees 的多次往返。
- 实现细节（`providers/codegraph_ai.py`）：subprocess 一次性模式
  `codegraph-server --graph-only --workspace <repo_root> --run-tool codegraph_get_call_graph --tool-args '{"uri":...,"line":...,"depth":1}'`；
  超时、JSON 解析失败、非零退出 → 该次跳过并记诊断日志（§1.7 诊断计数），**不抛异常中断扫描**。

### 1.3 引擎调用策略与性能纪律

- **调用粒度**：仅对 canonical **function 节点**（含方法）逐个取边（module 级调用由 scanner 覆盖，引擎无此能力）；`depth=1`。
- **执行方式**：顺序执行（v1 不做并发；one-shot 进程启动 + 增量索引已有持久层，POC 实测冷启后单次 1–3s）。
- **性能预算（M2 实测项）**：自扫描 dogfood（InsightGraph 自身 ~300 个可调用节点）目标 ≤15 分钟；超预算的优化路径 = `--serve` 常驻或批量策略（M3 备选，不在本次设计展开）。
- **版本与资产**：`probe` 时记录 `version`、`asset_hash`（二进制 sha256）进 `provenance`（§4.2）；引擎版本 pin 策略 = 设置项 `codegraph_engine_path` 指向固定路径，升级需人工更换并重新扫描。

### 1.4 raw DTO 与解析纪律

- `raw_models/symbol.py`：`RawLocation{file,line,end_line,column,end_column}`、`RawSymbol{id,name,kind,signature,path,line_start,line_end}`。
- `raw_models/relation.py`：`RawCallEdge{from_id,to_id,type}`、`RawCallGraph{nodes,edges,root}`、`RawEntryPoint{entry_type,node_id,symbol,...}`（当前不使用，保留解析能力供 M3 对比诊断）。
- 解析纪律：**`extra="ignore"`**（外部 schema 演进不致命）；缺字段/类型不符 → 跳过该条 + 诊断计数；不猜测不补造。

### 1.5 Adapter 映射职责（七组件）

| 组件 | 输入 → 输出 | 规则要点 |
| --- | --- | --- |
| `identity.py` | 引擎节点（path/line/kind/name）→ canonical node id | §1.6 匹配规则；匹配失败 → 丢弃该边 + 诊断计数 |
| `symbol_mapper.py` | 引擎 kind → canonical `NodeKind` | `Function`→function（方法亦是）、`Class`→class；其余丢弃（1-A：扩类不进入对外契约） |
| `relation_mapper.py` | 引擎边 type → `EdgeKind` | 白名单：`calls`→CALLS；`contains`→**丢弃**（与 DEFINES 同义，本仓 DEFINES 为准）；`imports`→丢弃（步骤 4 已有）；白名单外丢弃 |
| `span_mapper.py` | 引擎行号 → `SourceSpan` | 调用点证据不来自引擎（实测不可得，见 POC §专项）；仅节点定位用。输出行号按 **POC 实测口径（1-based，与编辑器一致）** 解释并做「±1 窗口 + 名称」双重匹配容错；输入 `line` 参数按官方文档 0-indexed 传 `span.line_start - 1` |
| `resolution.py` | 边来源与形态 → `CallResolution` | 引擎边 → `resolved`（POC 实测 0 假阳性）；scanner 四态判定见 §2；合并优先级见 §1.7 |
| `provenance.py` | probe 结果 → `ProviderRecord` | `{name, version, asset_hash, tools_used}`；未启用/不可用 → 空 provenance |
| `canonicalize.py` | CallFact 集合 → `CodeEdge` / `EntryPoint` 元组 | 分组、去重、代表 span、排序（§1.7/§3.5/§4.5） |

### 1.6 引擎节点 → Canonical 匹配规则

按序尝试，命中即止：

1. `path` 转为仓库根相对 POSIX 路径（大小写不敏感比较，兼容 Windows 盘符）。
2. kind 映射后，在**同文件节点**中按「行号窗口 ±1 包含」匹配（引擎 `line_start` 落在节点 span 内或边界 ±1）。
3. 多命中 → 名称相等者优先；仍多命中 → 全丢弃 + 诊断计数（宁缺勿错）。
4. `end_column=10000` 等哨兵值不参与判定。

### 1.7 合并策略（engine ∪ scanner）

合并单位 = 边键 `(source_id, target_id)`（ADR-010：同一关系只保留一条，冻结）：

```text
facts = scanner_facts（§2/§3 判定产物）+ engine_facts（适配后的 resolved 出边）
group by (source_id, target_id):
    resolution   = 优先级最高者：resolved > ambiguous        # dynamic/unresolved 不产生 fact
    source_span  = 全部贡献 fact 中 (line_start, line_end) 最小者（确定性代表 span，§3.5）
    is_truncated = 任一 fact 截断 且 合并后 resolution == ambiguous；合并为 resolved 时为 False
只保留 endpoints 均在 canonical 节点集内的边；自环跳过（沿用既有纪律）
edges 按 id 排序输出
诊断（仅日志，不进契约）：engine_only 边数、scanner_only 边数、两端丢弃数、
「engine 边与 scanner dynamic/unresolved 判定冲突」计数
```

### 1.8 降级纪律（不新增错误码）

- 引擎不可用/超时率异常 → 本扫描以 **scanner-only** 完成：`provenance` 留空、不再尝试引擎调用；扫描状态不受影响（不报错、不失败）。
- 「不虚假成功、不静默」的落点：① provenance 缺失即表明未用引擎；② 诊断日志记录跳过原因与计数；③ ADR-011 错误码闭集**不变**（无新码、无 severity 扩展）。

### 1.9 配置（Settings 新增）

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `codegraph_engine_enabled` | `False` | 显式开启（默认关闭 → 测试/CI 确定性不受引擎影响） |
| `codegraph_engine_path` | `""` | 引擎二进制路径（如 `D:\.codegraph\bin\codegraph-server-win32-x64.exe`） |
| `codegraph_engine_timeout_seconds` | `30` | 单次工具调用超时 |

`.env.example` 增补三个可选键与注释（机器相关路径不入库）。

---

## 2. 四态判定规则表

### 2.1 总则

1. **闭合与保守**：仅当目标集合可**确定性枚举**且非空时可判 `resolved`（|候选|=1）或 `ambiguous`（2..5）；（0 候选且目标显然在仓库外/不存在）→ `unresolved`；目标由运行时机制决定（参数值、getattr、元类等）→ `dynamic`。
2. **判定顺序**：先形态（是否 dynamic 构造）→ 再候选枚举（解析绑定）→ 再定级。
3. **不建边**：`dynamic` / `unresolved` 只进漏斗计数；`ambiguous` 物化候选边 + 防爆护栏（§2.4）。
4. **对称性**：同一调用点在 callers/callees 双向查询中必须得到一致状态（由单一 CallFact 数据结构保证）。

### 2.2 规则表（v1 已冻结）

| #   | AST 构造（callee 形态）                                                | 判定                                | 候选枚举来源                                                          | 说明                                                           |
| --- | ---------------------------------------------------------------- | --------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------ |
| R1  | `Name(...)` 直呼                                                   | resolved / ambiguous / unresolved | 模块绑定表：`def` 本模块 + `from M import f`                             | 命中 1 个 → resolved；同名多定义（`#n`）→ ambiguous；仓库内无候选 → unresolved |
| R2  | `Attr(Name=模块绑定)(...)`（`helpers.shout(...)`）                     | 同上                                | `import a.b` / `import a.b as m` / `from . import m` 的模块绑定      | 模块节点内查同文件函数；`m.attr` 中 attr 是模块内函数 → 1 候选                    |
| R3  | `Attr(Name=导入别名)(...)`（`g(...)`，`from M import f as g`）          | 同上                                | 别名绑定 → 目标函数                                                     | POC 盲区，scanner 主责                                            |
| R4  | `Attr(Name=self)(...)`（`self._format(...)`）                      | resolved / unresolved             | 本类方法表（同一 ClassDef）；找不到 → unresolved                             | v1 不做 MRO（基类方法留 v2.x，随 INHERITS 批次）                          |
| R5  | `Name(局部变量)(...)` 且局部变量为**单一直接赋值** `x = Cls(...)`；`Attr(x)(...)` | resolved / unresolved             | 浅层类型推断：函数体内该名字唯一一次赋值给 `Cls(...)` → 在 `Cls` 类方法表找 attr           | 多处赋值/条件赋值/链式 → unresolved（v1 不做多来源推断）                        |
| R6  | `Cls(...)` 类实例化                                                  | resolved                          | 目标类节点；若类定义了 `__init__` → **重定向到 `__init__` 函数节点**，否则指向 Class 节点 | 修正引擎的 Class 目标口径                                             |
| R7  | `Name(形参)(...)` / `Attr(形参)(...)`（`callback(...)`）               | **dynamic**                       | —（不枚举）                                                          | **修正夹具初步意向**（原标 ambiguous）：运行时决定，v1 不做栈间数据流；见 §2.5           |
| R8  | `getattr(...)(...)`、映射取值后调用（`d[k]` 形式）、`Call(...)(...)`（调用返回值）   | dynamic                           | —                                                               | 动态构造                                                         |
| R9  | stdlib / 第三方（`os.path.join(...)`）                                | unresolved                        | —（仓库内无候选）                                                       | 不建边，进漏斗                                                      |
| R10 | 模块级调用（main guard 内 `main()`、模块顶层语句中的调用）                          | resolved / ...                    | 同 R1–R3；**source = module 节点**                                  | 模块节点作为调用源（引擎不覆盖）                                             |
| R11 | `super().m(...)`                                                 | unresolved                        | —                                                               | v1 不解析 MRO；v2.x 评估                                           |
| R12 | 装饰器使用（`@decorator`）                                              | **v1 不采集**                        | —                                                               | 记入已知限制（§6 开放问题）；只采集 `ast.Call` 表达式                           |
| R13 | 嵌套函数（`<locals>`）内调用                                              | 同 R1–R10                          | 绑定 = 模块绑定 + 外层遮蔽（nearer 优先）                                     | source = 嵌套 function 节点                                      |

### 2.3 候选枚举细则

- **模块绑定表**（每文件）：`import a.b` → 绑定 `a`；`import a.b as m` → 绑定 `m` → 模块名 `a.b`；`from M import x` → 绑定 `x` → (M 内符号 x)；`from M import x as y` → 绑定 `y` → (M 内符号 x)；相对导入按层级上溯（复用 `python_ast._import_from_base` 同款规则）。
- **模块解析**：精确匹配 → 唯一包边界后缀匹配（1 个）→ resolved；**后缀匹配 2..5 个 → ambiguous（多候选）**；0 或 >5 个 → unresolved / 截断。
- **同名多定义**：目标 (kind, name) 在本模块存在 `#n` 多个 → 全候选集判 ambiguous（≤5）。
- **实例化重定向（R6）**：`Worker` 类节点的 `__init__` 方法按 `Class.qualname + ".__init__"` 查找。

### 2.4 防爆护栏（grill Q5 口径固化）

- ambiguous 候选上限 **5**/调用点：按候选 ID 升序**截断取前 5** 物化，贡献边 `is_truncated=True`；
- `ScanStats.oversized_ambiguous_calls` 计数（候选数 >5 的**调用点**数）；
- `dynamic` / `unresolved`：不建边、只进 `calls_dynamic` / `calls_unresolved` 计数（调用点粒度）。

### 2.5 与夹具初步意向的差异修正（需人工复核）

| 夹具行（`golden-python-calls/README.md` 初步意向） | 本设计口径 | 理由 |
| --- | --- | --- |
| 高阶回调 `callback(...)` → ambiguous | **dynamic** | 形参目标由运行时传入决定，候选集不可静态封闭；「不把动态推测伪装成确定」（完成门槛） |
| `worker.run()` → 待定 | **resolved**（R5 浅推断：单一直接赋值） | 夹具正是该浅推断的最小语言；不确定形态落 unresolved |
| ambiguous 形态覆盖 | **需补充探针**（实施 M1 时加入夹具，人工复核） | 原 ambiguous 行修正为 dynamic 后，夹具缺少 ambiguous 语料；建议探针：同模块重名函数（`#n`）被调用，或后缀歧义导入 |

> 期望冻结走既有纪律：evaluator 生成候选 → 人工逐项复核 → 冻结（`eval/README.md`）。

---

## 3. AST 调用补扫器设计

### 3.1 输入/输出与复用

- **输入**（进程内、由 `PythonAstAnalyzer` 传递，不新增文件 IO）：`parsed_files: list[_ParsedFile]`（含 tree/module_name/path）、`module_names: set[str]`、**符号表**（新增：`(kind, qualified_name, occurrence, node_id)` 全量清单，在 `python_ast.py` 构图时顺手产出）。
- **输出**：`CallFact` 列表
  ```python
  @dataclass(frozen=True)
  class CallFact:
      source_id: str            # 调用者节点（function 或 module）
      target_id: str            # 候选目标节点（每候选一条）
      resolution: CallResolution  # resolved / ambiguous（dynamic/unresolved 不进 fact）
      call_span: SourceSpan     # 调用表达式 span（§3.4）
      is_truncated: bool = False
  ```
  以及 `CallFunnel`（dynamic/unresolved/oversized 计数）。
- **复用**：`_ParsedFile` 已有 `tree`/`module_name`/`path_text`；模块解析复用 `_resolve_module`/`_import_from_base` 同款规则（提取为公共函数避免重复实现）。

### 3.2 绑定模型（`scanner/binding.py`）

三层作用域解析，就近遮蔽：

1. **模块层**：import 绑定表（§2.3）+ 模块顶层 def/class 名（含 `#n` 多定义）；
2. **类层**：类方法表（含 `#n`）；`self` 识别（`self` 为首参的方法体内）；
3. **函数层**：参数名集合 + 局部赋值记录（R5 浅推断用；单一直接赋值才记录类型）。

不建完整符号表/不做控制流——**只做形态确定性的浅解析**，任何不确定 → 保守降级（unresolved/dynamic）。

### 3.3 调用点采集

- 遍历范围：每文件 `ast.walk`，命中 `ast.Call` 即采集；**source 归属** = 包含该 Call 的最近定义节点（function/方法；无则 module 节点）——用 `_nested_blocks` 同款作用域下潜得到定义 span 栈。
- callee 形态分类 → 按 §2.2 规则表（R1–R13）判定；每条 Call 产出 0..N 个 CallFact + 漏斗计数。
- 确定性：按 `(source_id, call_span.line_start, call_span.line_end)` 排序遍历；候选按 ID 升序。

### 3.4 call-site span 口径

- `span = SourceSpan(file_path=当前文件, line_start=call.lineno, line_end=call.end_lineno)`（多行调用自然覆盖）。
- **列号不做**（列号 v1 不承诺，P7 已决）；`end_column` 不引入。
- 与符号 span 的区别在文档与字段名（`CodeEdge.source_span`）中显式标注。

### 3.5 去重与代表 span 规则（关键取舍）

- ADR-010 冻结：同一 `(kind, source, target)` 只保留一条边（`build_edge_id` 保证）。**同一对 (src,dst) 的多个调用点无法逐点建边**。
- 规则：合并后 `source_span` = 贡献 fact 中 `(line_start, line_end)` 字典序最小者（确定性「代表 span」）；`resolution` 取优先级最高；`is_truncated` 见 §1.7。
- 被否方案：①边携带 span 列表 → 破坏边身份与冻结格式；②逐调用点建边 → 边 ID 撞车且违反去重纪律。**已知代价**：v1 不表达「同关系多调用点」的逐点证据；如需逐点回溯，v2.x 再评审（与 P6 同批次的复审触发一并记录）。

### 3.6 模块级与嵌套调用

- 模块级 Call（如 main guard 体内 `main()`）→ source = module 节点（R10）；模块节点此前无出边先例，DEFINES/imports 语义不受影响。
- 嵌套函数：`__qualname__` 含 `<locals>`（步骤 4 口径），binding 遮蔽按 AST 父链传递。

### 3.7 确定性要求

- 全部输出可重跑自比（字节级）：排序键固定、候选排序固定、无时间戳/无随机。
- 局部失败（单文件语法错误）不影响其余文件（沿用步骤 4 隔离纪律；出错文件不产出 CallFact）。

---

## 4. schema v2 契约变更清单

> 一次升级（schema_version 1→2）承载全部变更；不得拆分为多次。变更经受控流程（ADR-010 §4 同款）。

### 4.1 `domain/codegraph/kinds.py`

```python
class EdgeKind(StrEnum):          # CALLS 注释更新：第二阶段（步骤 5）已实现
    DEFINES = "defines"; IMPORTS = "imports"; CALLS = "calls"

class CallResolution(StrEnum):    # 新增（闭集；新值=契约变更）
    RESOLVED = "resolved"; AMBIGUOUS = "ambiguous"
    DYNAMIC = "dynamic"; UNRESOLVED = "unresolved"

class EntryKind(StrEnum):         # 新增（闭集）；analyzer 侧 EntryPointKind 统一引用
    MAIN_GUARD = "main_guard"; WEB_APP = "web_app"
```

### 4.2 `domain/codegraph/models.py`

**CodeEdge（+3 字段 + 校验）**

| 字段 | 类型/默认 | 不变量 |
| --- | --- | --- |
| `source_span` | `SourceSpan \| None = None` | calls 边**必填**；非 calls 边必须为 `None` |
| `resolution` | `CallResolution \| None = None` | calls 边**必填**且 ∈ {resolved, ambiguous}（dynamic/unresolved 不建边）；非 calls 边必须为 `None` |
| `is_truncated` | `bool = False` | 仅当 calls 且 resolution==ambiguous 可为 True；其余必须 False |

**新增 `EntryPoint`（图级清单记录）**

```python
class EntryPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: EntryKind
    module_id: str                       # 必须引用 module 节点
    span: SourceSpan                     # MAIN_GUARD=if 语句 span；WEB_APP=赋值语句 span（含装饰器不起作用，语句起点）
    symbol: str | None = None            # main_guard=函数名；web_app=变量名
    target_node_id: str | None = None    # main_guard 可解析到本模块顶层函数节点时给出；web_app 为 None
```

**新增 `ProviderRecord`（扫描级 provenance）**

```python
class ProviderRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str; version: str
    asset_hash: str | None = None        # 形如 "sha256:<64hex>"（可核验时）
    tools_used: tuple[str, ...] = ()     # 例如 ("get_call_graph",)
```

**CodeGraph（+2 字段 + 校验）**

| 字段 | 默认 | 不变量 |
| --- | --- | --- |
| `entries` | `tuple[EntryPoint, ...] = ()` | `module_id` 引用存在且为 module 节点、同文件 span；`target_node_id`（若有）引用 function 节点且同文件；按 `(module_id, span.line_start, span.line_end, kind)` 升序唯一 |
| `provenance` | `tuple[ProviderRecord, ...] = ()` | 按 `name` 升序唯一；scanner-only 时为空 |

- `schema_version`：新产出一律为 **2**；`parser_version` → `python-ast/0.2`（两者相互独立，ADR-010）。
- 既有节点/边校验不变（ID 构造、去重、引用完整性）；v1 工件语义保持有效（历史工件按 v1 解读）。

### 4.3 application 契约（`application/scans/`）

```python
# models.py
class CallFunnel(BaseModel):                 # 新增（frozen/extra=forbid）
    calls_dynamic: int = Field(default=0, ge=0)          # dynamic 调用点数
    calls_unresolved: int = Field(default=0, ge=0)       # unresolved 调用点数
    oversized_ambiguous_calls: int = Field(default=0, ge=0)  # 候选>5 的调用点数

class AnalyzeOutcome(...):
    call_funnel: CallFunnel | None = None    # 新增可选字段

class ScanStats(...):
    calls_dynamic: int = Field(default=0, ge=0)              # 新增
    calls_unresolved: int = Field(default=0, ge=0)           # 新增
    oversized_ambiguous_calls: int = Field(default=0, ge=0)  # 新增

# service.py
_build_stats(...):  # 增参 call_funnel；funnel 缺失时三计数保持 0
```

- **口径纪律**：resolved/ambiguous 计数**不入 stats**（可从图推导：按边统计）；stats 只存不可推导值（`calls_dynamic` / `calls_unresolved` / `oversized_ambiguous_calls`）。
- 未解析比例（可重复测量）定义：`(calls_dynamic + calls_unresolved) / (calls_dynamic + calls_unresolved + |calls 边|)`（分母为边数的近似口径，文档标注；站点级精确比例留 v2.x）。

### 4.4 校验器增量

- **域校验器（models.py）**：§4.2 三条不变量 + entries/provenance 引用与排序。
- **`eval/codegraph/validate.py`**：新增两类检查（与域校验同源）——
  4. 每条 calls 边必须携带 source_span 与 resolution，且 resolution ∈ {resolved, ambiguous}；
  5. entries 的 module_id / target_node_id 引用存在且文件一致。
- 既有三项检查（DEFINES 入边 / content_hash / imports 目标）不变。

### 4.5 排序与确定性

- edges：仍按 `edge.id` 升序（不变）；nodes 不变。
- entries：`(module_id, span.line_start, span.line_end, kind)` 升序。
- provenance：`name` 升序。
- 空图/无 entries/无 provenance 的序列化形状固定（空数组而非缺省字段）。

### 4.6 影响面与同步位点

| 位点 | 动作 |
| --- | --- |
| `golden-python-basic` | 分析器行为变化 → expected 需重建：AI 生成候选（新增 CALLS/entries）→ **人工逐项复核** → 冻结（eval/README 纪律）；DEFINES/IMPORTS 语义集合必须零回归 |
| `golden-python-calls` | 期望冻结（含 §2.5 修正口径 + 补充 ambiguous 探针）+ 指标扩展 |
| `evaluator.py` | 语义比对纳入 CALLS（键含 resolution）与 entries；新增指标：calls precision/recall、未解析比例（§4.3 口径） |
| `baselines/` | **新建** `v2`（不覆盖 v1）；v1 保留 |
| 文档 | CLAUDE.md §二（五类节点/边说明）、architecture.md §5.1、ADR-010 §4（引用 v2）、Development Plan 步骤 5 |
| 测试 | 域模型/校验器新单测；scanner 单测（规则表逐行）；adapter 单测（用 POC raw JSON 做 fixture 输入——`eval/codegraph/.outputs` 属本地证据，入库副本放 `backend/tests/unit/infrastructure/fixtures/`）；merge 单测（representative span / 优先级 / 截断） |

### 4.7 兼容纪律

- 无新错误码（ADR-011 闭集不变）；引擎降级不产生错误（§1.8）。
- 旧 v1 工件：保留读取语义；新解析一律 v2。
- `extra="forbid"` 沿用：v2 工件在 v1 代码上加载会失败——**这是设计意图**（防止静默降级解读）。

---

## 5. 实施里程碑与验收

| 里程碑 | 内容 | 验收（可执行） |
| --- | --- | --- |
| **M1**（scanner 自足闭环） | 契约 v2（§4）+ scanner（§2/§3）+ entries + funnel；golden-python-calls 期望冻结；basic expected 复核更新；Baseline v2 | 夹具契约口径 100%（resolved/ambiguous/dynamic/unresolved 全对）；basic 六项不变量通过 + DEFINES/IMPORTS 零回归；evaluator 100%；自扫描 dogfood 零错误；ruff/mypy/pytest 全绿 |
| **M2**（引擎接入） | provider + adapter + merge（§1）；降级路径；Settings | 夹具上「引擎并入 ≡ scanner-only 结果」（幂等合并证明）；provenance 正确写入；关引擎/坏路径降级测试通过；自扫描耗时记录（性能预算） |
| **M3**（落账） | ADR-012 v2（并入本设计主体）落 `docs/adr/`；架构/CLAUDE/Plan 同步；CI linux 引擎明确豁免；若 M2 自扫描超过 15 分钟则引入 `--serve` 常驻方案 | 文档同步矩阵全部勾选；死链/CI 全绿；Human 评审记录；性能超预算时 `--serve` 验证通过 |

---

## 6. 评审冻结结论

1. **引擎行号口径**：M2 在更多样本复验后固化 `span_mapper`；当前保留 ±1 窗口兜底。
2. **CI 与引擎**：CI 只运行 scanner + mock provider；真实引擎验证留在本地 dogfood，不引入 CI 外部资产依赖。
3. **性能预算**：M2 先实测自扫描是否超过 15 分钟；若超时，M3 引入 `--serve` 常驻方案并验证。
4. **v2.x 边界**：装饰器调用、`super()`、MRO/继承链、逐调用点证据不阻塞本批次，随 INHERITS/IMPLEMENTS 批次评审。
5. **ambiguous 探针**：使用同模块重名（`#n`）形态，期望结果由 Human 人工复核后冻结。

---

> 起草：2026-10-07（Agent）｜评审冻结：2026-10-08（sixmoon）｜后续：契约变更实施（M1）+ ADR-012 v2 落账（M3）。
> 关联：[决策文档 §16](codegraph-adapter-selection-and-evolution.md)（契约决策记录）、[选型文档 §6](codegraph-oss-adoption.md)（ADR 草案）、[金夹具说明](../../eval/codegraph/cases/golden-python-calls/README.md)。
