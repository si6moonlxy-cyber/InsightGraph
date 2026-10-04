# CodeGraph CALLS 前置调研：开源调用图 / CodeGraph 项目参考笔记

> 状态：步骤 5 前置调研交付物（设计开工前的参考与决策输入）
> 日期：2026-10-03 ｜ 数据快照：2026-10-03（许可证 / 归档标志 / 最近推送均为当日快照，会随时间变化）
> 关联：[Development Plan](../Development%20Plan.md) 步骤 5 前置调研；[ADR-001](../adr/ADR-001-codegraph-graphrag-boundary.md) / [ADR-006](../adr/ADR-006-codegraph-json-artifact-first.md) / [ADR-010](../adr/ADR-010-codegraph-contract-discipline.md) / [ADR-011](../adr/ADR-011-scan-result-contract.md)
> 纪律边界：本次只调研——未引入任何第三方依赖、未修改已冻结契约、未写产品代码；契约变更与依赖引入仅以「借鉴-否决清单 / ADR 草案」形式提议，等 Human 决策。所有结论附证据链接（见 §6）。
>
> **修订记录（2026-10-04）**：主要矛盾经 Human feedback 修订为「借鉴并使用开源项目，快速开展 CodeGraph 代码解析功能」。
> 选型结论与 ADR 草案已重做：最新以 [codegraph-oss-adoption.md](codegraph-oss-adoption.md) 为准（Engine → Adapter → 本仓库 Artifact 路线，含 codegraph-ai/CodeGraph 核实与 POC 计划）；
> feedback 原文见 `CodeGraph CALLS 前置调研 - feedback.md`。本文 §2 / §3 保留为研究资料（机制对比仍然有效）。

## 1. 调研范围与核实口径

候选项目与结论总览：

| 项目          | 类型                             | 许可证（快照）                                   | 维护状态（快照）                                 | 结论                |
| ----------- | ------------------------------ | ----------------------------------------- | ---------------------------------------- | ----------------- |
| PyCG        | 学术调用图工具（ICSE'21）               | Apache-2.0                                | **已归档**（最后推送 2023-11-26，README 明示不再开发）   | 机制借鉴，不引依赖         |
| JARVIS      | 学术调用图工具（arXiv 2305.05949）      | **无许可证**（无 LICENSE 文件）                    | 未归档（最后推送 2026-03-22；项目页称论文投 TOSEM）       | 仅方法论参考            |
| HeaderGen   | 学术工具（SANER 2023，扩展 PyCG）       | **无许可证**（无 LICENSE 文件）                    | 未归档（最后推送 2025-01-30）                     | 仅方法论参考            |
| astroid     | Python AST 解析 + 推断库（pylint 内核） | LGPL-2.1                                  | 活跃（最后推送 2026-09-30）                      | 接口设计借鉴；依赖引入设触发点   |
| griffe      | Python API 静态抽取库（mkdocstrings） | ISC                                       | 活跃（最后推送 2026-10-02）                      | 别名解析设计借鉴；依赖引入设触发点 |
| SCIP        | 代码索引协议（Protobuf），含 scip-python | 协议 Apache-2.0；scip-python MIT（pyright 派生） | 活跃（协议 2026-10-02；scip-python 2026-10-02） | 设计原则引用；不引格式/运行时   |
| LSIF        | 索引协议（SCIP 前身）                  | —                                         | **已废弃并移除**                               | 否决                |
| Sourcetrail | 交互式源码浏览器（C++/Qt）               | GPL-3.0                                   | **已归档**（2021 年底，最后推送 2021-12-13）         | 否决（仅 UI 理念参考）     |
| pyan3       | 静态调用图生成器                       | GPL-2.0                                   | 活跃（最后推送 2026-09-21）                      | 否决（许可证 + 分析浅）     |
| code2flow   | 多语言调用图可视化                      | MIT                                       | 未归档（最后推送 2025-07-27）                     | 启发式策略借鉴；不引依赖      |
| tree-sitter | 增量容错解析框架                       | MIT                                       | 极活跃（最后推送 2026-10-02）                     | 观察项；第二解析器触发点      |
| rustworkx   | Rust 核心图算法库（Python 绑定）         | Apache-2.0                                | 活跃（最后推送 2026-09-28）                      | 观察项；图算法需求触发点      |

**与 ADR-001（图分离）的契合度**：上述工具均为**纯代码结构 / 索引工具**，不含 Technology / Claim / Evidence 知识层——引入（若未来发生）不会诱发 CodeGraph 与 GraphRAG 混合；唯一需要警惕的用法是把 CodeGraph 产物直接当作知识点真源，本次借鉴清单未列入任何此类用法。SCIP 的「索引 ≠ 存储 ≠ 知识」边界（DESIGN.md）恰好佐证 ADR-001 的分层逻辑。

核实口径：

- 许可证与维护状态：GitHub API（`license` / `archived` / `pushed_at`）＋ 仓库内 LICENSE 文件实际内容（"无许可证"指两者皆缺，默认保留全部权利，**代码不可复用**）。
- 机制描述：官方 README / 论文 / 官方文档；评测数据引用论文原文数字。
- 本文所有数字与判断均为 2026-10-03 快照，复核时以仓库当前状态为准。

### 关联现状：步骤 5 先行件（2026-10-03 已落地）

调研期间，仓库落地了两个**不依赖调研结论**的步骤 5 先行件（commit `5a969fa`，均未触碰冻结契约）：

- 入口识别规则：`backend/app/infrastructure/analyzers/entry_points.py`（main guard / FastAPI `web_app`，仅识别、无产物表示）+ 10 项规则测试；
- CALLS 语料夹具：`eval/codegraph/cases/golden-python-calls/`（调用形态矩阵，**期望结果未冻结**；其初步意图与本文 §3.1 的四态口径同向：跨模块直呼 / 模块属性 / 实例化 / 别名 → resolved，高阶回调 → ambiguous，`getattr` → dynamic，stdlib → unresolved 不建边）。

本调研把二者作为对齐对象：§5 的 ADR 草案即为其「表示层与判定口径」的落账前置；入口识别的**产物表示**（节点标记 / 新边类型 / 独立清单）属待决策项（见 §7）。

## 2. 参考笔记（逐项目）

### 2.1 PyCG（vitsalis/PyCG，ICSE'21）

- **定位**：实践导向的 Python 静态调用图生成器（precision 优先），ICSE 2021 论文随工具发布；无第三方依赖（纯 stdlib）。
- **关键机制**：对中间表示做**上下文不敏感**的过程间分析，用**不动点迭代**构建**赋值图**（assignment graph：程序标识符之间的赋值关系，含 func / var / cls / mod 四类对象）；分析状态 = 赋值图 + 作用域树 + 类层次 + 当前命名空间。要点：
  - 属性访问按**定义所在命名空间**区分（同名方法在不同类中不混淆）——对比同名字段式分析（JavaScript 传统）的精度提升来源；
  - 类层次保留**父类顺序**以支持 MRO（多重继承方法解析）；
  - `import x from m as y` 建模为别名赋值边，导入解析可**自动跟进可导入的依赖模块**；
  - 生成器建模为 thunk（迭代时才求值）；dict/list 当作普通对象；条件/循环保守处理（两分支都算，不做路径敏感）。
  - 调用图构建：终态后在 IR 上再走一遍，对每个调用点取 `getReachableFuns(π, callee)` 的**全部可达函数**作为被调候选。
- **评测（论文数字）**：微基准 112 例 / 16 类别（论文 Table I：parameters 6、assignments 4、built-ins 3、classes 22、decorators 7、dicts 12、direct calls 4、exceptions 3、functions 4、generators 6、imports 14、kwargs 3、lambdas 5、lists 8、mro 7、returns 4）。论文口径：无假阳性（"complete"）111/112；无假阴性（"sound"）103/112（注意：论文对 complete/sound 的定义与通常用法相反，引用时需带定义）。宏基准（5 个真实项目，人工 gold）：precision ≈ 99.2%，recall ≈ 69.9%；性能约 0.38s/1k LoC。
- **优缺点**：优点是 precision 高、无依赖、微基准可复用；缺点是**输出为 may-call 邻接表**（`{node: [callees]}`，无状态区分），流程不敏感，starred 赋值等场景漏报（recall 受限），**已归档**（README："no further development improvements are planned"）。
- **许可证 / 维护**：Apache-2.0；archived=true；365 stars（快照）。
- **可借鉴点**：命名空间感知解析、MRO 有序父类链、导入别名赋值边、thunk 化生成器、微基准 16 类别清单、precision/recall 评测口径。
- **结论**：机制借鉴；不引依赖（归档 + 无 span/状态模型 + 与确定性序列化契约不兼容）。

### 2.2 JARVIS（pythonJaRvis，arXiv 2305.05949）

- **定位**：面向**应用中心**（application-centered）的可扩展精确调用图（论文标题 "Scalable and Precise Application-Centered Call Graph Construction for Python"；项目页称论文已投 TOSEM）。
- **关键机制**：为每个函数维护**类型图（FTG，function type graph）**支撑类型推断；**按需（on-the-fly）逐函数**生成调用图，过程内流敏感分析 + 过程间分析交替进行，执行**强更新**（strong update）；为 if/while/try 建立控制流结构；`with` / `for` 分别脱糖为 `__enter__` / `__exit__` 与 `__iter__` / `__next__` 调用（见项目页 Transfer rules）。提供 E.A. / A.W. 两种模式（是否跟进依赖库分析）。
- **评测（论文摘要数字）**：微基准 135 个小程序 + 6 个真实应用；相比 PyCG 至少快 67%、精度高 84%、召回高 20%；论文指出 PyCG 对超过 2000 行的程序可能 OOM 或超时（全局不动点迭代代价）。
- **优缺点**：优点是流敏感 + 类型图显著提升精度与召回；缺点是复杂度高、实现重（类型图 + CFG + 按需分析）、**无许可证**（不可复用代码）、工程化程度低（研究原型）。
- **许可证 / 维护**：无 LICENSE 文件（GitHub API license=null；raw LICENSE 404）；未归档但属研究原型；fork `nuanced-dev/jarviscg` 已归档，同样无许可证。
- **可借鉴点**：应用中心边界（分析应用 + 依赖则显式开关，如 A.W. 模式）；协议方法脱糖建边（with/for → dunder 调用）；"按需逐函数" 与"全量不动点" 的成本对照。
- **结论**：仅方法论参考（无许可证；不复制代码、不引依赖）。

### 2.3 HeaderGen（secure-software-engineering，SANER 2023）

- **定位**：Jupyter Notebook 静态分析工具（自动加节标题），其调用图能力是 **PyCG 的扩展版**（仓库内 `pycg_extended/`）。
- **关键机制**：在 PyCG 基础上增加**流敏感**分析与**外部库返回类型解析**——用 typestub 数据库（面向 ML/数据科学库）为库函数推断返回类型，解决"链式调用跨库后断裂"的问题；缓存类型数据（pickle）。
- **优缺点**：优点是在 PyCG 之上证明了"类型存根（typestub）可把外部库解析从不可能变为可行"，且外层（Notebook 叙事结构）与分析内核分层清晰；缺点是场景专用（Notebook + ML 库）、依赖重量级 typestub 数据、**无许可证**。
- **许可证 / 维护**：无 LICENSE 文件（license=null；raw LICENSE 404）；最后推送 2025-01-30；15 stars。
- **可借鉴点**：外部符号解析的"类型存根表"思路（未来若解析第三方库调用，可评估以独立数据源形式引入，而不是硬编码分析）；PyCG 可被增量增强（流敏感、外部类型）的架构示范。
- **结论**：仅方法论参考（无许可证；场景不匹配 MVP）。

### 2.4 astroid（pylint-dev/astroid）

- **定位**：Python AST 解析 + **静态推断** 库，pylint 的解析内核（"currently powering most of pylint capabilities"）。
- **Wrapper 形态**：`astroid.parse(source)` 形态与 stdlib `ast` 类似（`Module` 等 NodeNG 家族）；在此之上提供：
  - `node.infer()` —— **返回生成器**，迭代"该节点可能取到的所有值"；与 stdlib 的关键差异是**推断失败是一等值**（`Uninferable` 单例，表示"跟丢了"），而非抛异常；推断出的实例是 `Instance` 包装；
  - 推断系统可经 **inference transforms** 扩展（文档含《Extending astroid syntax tree》专页）；`AstroidManager` 提供缓存与转换注册；
  - `InferenceError` 异常家族 + `CallContext` / `InferenceContext`（调用参数上下文）；
  - 文档示例可完整求值 `a + b`（常量折叠），体现"部分解释器"定位。
- **优缺点**：优点是与 pylint 共同久经生产验证、推断覆盖面广、扩展机制成熟；缺点是**重量级**（推断引擎 + 缓存 + 大量补丁式语义）、LGPL-2.1（作为库依赖可用，但引入需评审）、推断结果与"确定性字节级契约"之间需要额外纪律层。
- **许可证 / 维护**：LGPL-2.1；活跃（最后推送 2026-09-30）；584 stars；文档版本 4.4.0-dev0。
- **可借鉴点**：① 失败是一等值（`Uninferable`）而非异常传播——与我们的 `resolved/dynamic/unresolved` 状态化思路同构；② `infer()` 生成器接口（"可能值集合"）比"单值解析"更贴合 Python 语义；③ 推断上下文（CallContext）参数化设计；④ 扩展/转换注册表模式。
- **结论**：接口设计借鉴；依赖引入设触发点（见 §4 借鉴清单 B7 与 §5 决策点）。

### 2.5 griffe（mkdocstrings/griffe）

- **定位**：Python API 静态抽取（"Signatures for entire Python programs"），面向 API 文档与破坏性变更检测；**不是**调用图工具。
- **关键机制**：
  - 加载器：`load()` / `load_git()` / `load_pypi()`（静态 visit 与动态 inspect 两种代理）；
  - 模型：`Module` / `Class` / `Function` / `Attribute` / **`Alias`（指向另一模块中对象的间接层/别名）**；
  - 表达式：`Expr` 家族（ast 包装）+ `get_expression` / `safe_get_expression` 等**安全提取器**（safe 版失败返回 None 而不抛）；
  - 异常体系：`NameResolutionError`（作用域内名字无法解析）、`AliasResolutionError`、**`CyclicAliasError`（别名环检测）**、`UnimportableModuleError` 等——**解析失败是类型化异常，环是显式错误**；
  - 序列化 JSON、扩展系统、跨模块成员导航。
- **优缺点**：优点是**静态优先**（不需要 import 目标代码）、别名链 + 环检测的建模干净、ISC 宽松许可、工程活跃；缺点是只覆盖"表面 API"（不做体级数据流/调用解析），与本步骤的需求只是部分重叠。
- **许可证 / 维护**：**ISC**（注意：不是 MIT）；活跃（最后推送 2026-10-02）；696 stars。
- **可借鉴点**：① `Alias` 间接层（import 别名链 = module attr → module → 目标定义的解析模型）；② 解析错误类型化 + **别名环显式检测**（对应我们 import 环路场景）；③ `safe_*` 模式（默认不抛的保守解析）；④ 静态加载不执行代码的边界。
- **结论**：设计借鉴（别名/环/安全解析）；依赖引入设触发点。

### 2.6 SCIP 与 scip-python（scip-code/scip；sourcegraph/scip-python）

- **定位**：SCIP 是语言无关的**代码索引协议**（Protobuf schema + CLI + 多语言绑定），用于支持"转到定义 / 查找引用 / 查找实现"；scip-python 是其 Python 索引器（**pyright 的 fork**，npm 分发）。
- **关键机制**：
  - 索引数据以 **document + occurrence** 组织（每文件一组），符号用**字符串 moniker** 标识（跨仓库导航用 `<package> <version>` 命名空间保证稳定引用）；
  - scip-python 复用 **pyright 的类型推断**进行高保真符号解析（因此精度上限=类型检查器）；需要 **Node v16+**、Python 3.10+，经 pip 环境自省或 `--environment` JSON 提供包清单；
  - 官方设计文档（DESIGN.md）明确的核心决策：**协议是传输格式而非存储格式**；**避免直接编码图**（不用邻接表，用 document/array 便于流式与并行）；**避免整数 ID**（LSIF 的整数符号表曾出现 off-by-one 导致全仓导航失效；字符串 ID 把 bug 爆炸半径限制在局部）；对索引器 bug 的**爆炸半径控制**是显式目标。
- **优缺点**：优点是精度上限高（类型检查器级）、设计文档质量极高、生态广（多语言索引器）；缺点是**运行时沉重**（Node + pyright 全家桶 + npm 生态）、协议面向"导航"而非"结构分析 Artifact"、与我们的 Pydantic JSON 契约目标不同。
- **许可证 / 维护**：协议仓库 Apache-2.0（已从 sourcegraph/scip 迁至 scip-code/scip，820 stars，活跃）；scip-python：仓库 `LICENSE.txt` 为 **MIT**（pyright 上游授权，Microsoft copyright；GitHub 检测显示 NOASSERTION）；活跃（2026-10-02）。
- **可借鉴点**：① **字符串 ID / 避免整数编号** 与 ADR-010 决策同向（外部佐证）；② "传输格式 ≠ 存储格式"的边界思维（论证我们 JSON Artifact 作为自有存储格式 + 未来可单向导出）；③ 爆炸半径控制 → 我们已有 codegraph validate.py 不变量校验器的同理念（可继续强化）；④ moniker 携带包版本号的做法（跨版本引用稳定性，可作未来跨仓库引用设计的参考）。
- **结论**：设计原则引用（ADR-012 引用其佐证）；不引入 Protobuf 格式与 Node 运行时。

### 2.7 LSIF（已废弃）

- **状态**：Sourcegraph 官方已全面弃用并移除 LSIF 支持，推荐 SCIP 替代（DESIGN.md 脚注："LSIF support has since been fully deprecated and removed"；站点 lsif.dev 声明不再维护、已被 SCIP 取代；2022 公告博客建议新索引器直接产出 SCIP）。
- **结论**：否决（废弃协议，无引入理由）。

### 2.8 Sourcetrail（CoatiSoftware/Sourcetrail，已归档）

- **定位**：免费开源的交互式源码浏览器（C++/Qt 桌面应用），支持 C/C++/Java/Python，提供 SourcetrailDB SDK 供自定义语言扩展；Python 索引器为预编译二进制。
- **状态 / 许可证**：**2021 年底官方归档**（README 明示："archived by the original authors and maintainers ... by the end of 2021"；API archived=true，最后推送 2021-12-13）；GPL-3.0（名称商标不在 GPL 授权内）；16.5k stars。
- **可借鉴点**：图探索 UI 的交互理念（步骤 10 的图谱浏览器可作参考，例如"引用/被引用"双向浏览、子图聚焦）；SDK 式语言扩展架构（何时引入第二语言时的外围设计）。
- **结论**：否决（归档 + GPL-3.0 + GUI/DB 中心架构与本仓库 "图分离 / Artifact first / 头less 分析" 目标不符）；仅 UI 理念留待步骤 10。

### 2.9 pyan3（Technologicat/pyan，PyPI 名 pyan3）

- **定位**：老牌"离线调用图生成器"，PyCG 论文对比过的基线之一；静态分析较浅（论文描述："performs a rather superficial static analysis"）。
- **论文实测问题（PyCG ICSE'21 微基准）**：无假阳性（complete）43/112、无假阴性（sound）36/112；误报来源——对对象初始化**同时建类名与 `__init__` 两条调用边**、import 建"到模块名"的调用边；漏报来源——不追踪跨过程值流（参数/返回的函数不解析）、generators 与 exceptions 类别几乎全失。
- **优缺点**：优点是输出务实（DOT/GraphML 可视化）、持续维护至 Py3.14；缺点是分析浅、误报模式已知；**GPL-2.0 传染性**。
- **许可证 / 维护**：GPL-2.0；活跃（最后推送 2026-09-21）；457 stars。
- **结论**：否决（GPL-2.0 + 分析质量不足；如需画图可由我们自己的 Artifact 后续导出 DOT，不引依赖）。

### 2.10 code2flow（scottrogowski/code2flow）

- **定位**：面向动态语言的多语言调用图可视化（Python/JS/Ruby/PHP），强调"pretty good estimate"（README 自称无法做到完美，公开列出已知限制）。
- **关键机制（README 算法 8 步）**：AST → 分组（groups=文件/模块/类，即"函数所在的命名空间"）与节点（functions）→ 收集调用与**作用域内变量** → 变量到节点/组的启发式匹配 → 依次：作用域内唯一匹配 → 全局唯一匹配；**匹配不唯一时大声跳过**（同命名空间同名方法直接跳过并告警）；剪除孤儿节点/组；支持 `--target-function` + `--upstream-depth`/`--downstream-depth` 的**子图抽取**；输出 DOT（另有 SVG 等）。
- **优缺点**：优点是**诚实的模糊性策略**（说不清就跳过 + 告警，绝不静默猜）、孤儿分析、子图抽取；缺点是启发式、同名方法级解析能力弱（对 class 方法场景不可用）、通用语言支持牺牲 Python 细节（无 span 证据、无状态区分）。
- **许可证 / 维护**：MIT（注：2021-04 重写前的历史提交为 LGPL，重写后整体 MIT）；未归档（最后推送 2025-07-27）；4.6k stars。
- **可借鉴点**：① "模糊 → 显式跳过 + 计数/告警"的取舍纪律（与我们的 ambiguous/unresolved 统计同构）；② 孤儿/根节点分析（入口识别的反向视角）；③ 子图抽取参数（未来 API 层查询原语）；④ "无完美调用图"的预期管理（文档诚实度）。
- **结论**：策略借鉴；不引依赖（能力不匹配：无 span 证据、无状态化边、方法级精度不足）。

### 2.11 tree-sitter（tree-sitter/tree-sitter）

- **定位**：增量**容错**解析框架（Rust 核心 + 多语言 grammar），编辑器生态事实标准（GitHub、Neovim 等）。
- **与我们的关系**：我们把"语法错误"作为**局部失败通道**（`syntax_error`，单文件隔离）处理，stdlib `ast` 对合法文件已完全可用；tree-sitter 的价值场景是"**文件在编辑中/不完整时仍要产出部分结构**"与**多语言**支持。代价：C 工具链/wheel 依赖、CST 与 `__qualname__` 语义的映射需重新推导（我们当前分析器直接映射 AST 语义）。
- **许可证 / 维护**：MIT；极活跃（最后推送 2026-10-02）；27k stars。
- **结论**：观察项，**设触发点**——当"错误容忍解析"或"第二语言"成为真实需求（见 §4 否决清单 R12/B12），再评审引入；在此之前不引入。

### 2.12 rustworkx（Qiskit/rustworkx）

- **定位**：Rust 实现、Python 绑定的高性能图算法库（原 retworkx，Qiskit 出品），提供图/多重图数据结构 + 标准图算法（DAG 操作、中心度等，文档含 DAG 与 Betweenness Centrality 教程）+ 图生成器 + 布局/可视化辅助。
- **与我们的关系**：我们当前阶段（步骤 5）只有"小图 + 简单遍历"（邻接索引 + BFS 找入口/调用者），标准库 `dict[str, list[str]]` 足够；rustworkx 的价值在**规模化算法**（如大图 SCC、拓扑排序、中心度、最短路 —— 对应未来的影响分析/图查询）。
- **代价**：新依赖 + Rust 编译链（官方为常见平台发布预编译 wheel，其余平台需要 Rust 工具链）；引入即打破"零第三方依赖"现状（当前 backend 仅 FastAPI/Pydantic 栈）。
- **许可证 / 维护**：Apache-2.0；活跃（最后推送 2026-09-28）；1.8k stars。
- **结论**：观察项，**设触发点**——步骤 6/8 实测出现图规模性能问题或需要高级图算法时评审；届时与 NetworkX（纯 Python、BSD-3）一起做选型对比。

## 3. 四大必答问题综合回答

### 3.1 CALLS / 符号解析：各项目怎么做，如何区分状态，误报/漏报怎么取舍

**机制对比**（针对"本地函数 / 方法 / 导入别名 / 模块属性"四类调用）：

| 场景 | PyCG | JARVIS | code2flow | astroid | griffe |
|------|------|--------|-----------|---------|--------|
| 本地函数调用 | 作用域树 + 赋值图解析 | FTG 类型图按需解析 | 作用域内变量唯一匹配 | `infer()` 生成器 | （不做调用解析） |
| 方法调用 | 命名空间感知 + MRO 有序解析 | 流敏感 + 强更新 | 同名方法**大声跳过** | Instance 推断 + 类模型 | （不做） |
| 导入别名 | 别名赋值边（import 语句 → 边） | Import 转移规则 | 组匹配启发式 | Import/From 节点推断 | **Alias 间接层 + 环检测** |
| 模块属性 | 命名空间链解析 | Store/Load 转移规则 | 全局唯一匹配回退 | 对象模型（Module/Class） | 跨模块成员导航 |

**状态区分（resolved / ambiguous / dynamic / unresolved）**：调研对象**没有一个**提供与我们要求相同的四态模型——

- PyCG / JARVIS 输出 **may-call 集合**（论文口径下所有还原出的调用边都只是"可能"，`getReachableFuns` 一次可能返回多个目标，**不区分确定/歧义**）；
- code2flow 用"**跳过 + 告警**"处理歧义（不产出边的歧义在输出中不可见，只有日志）；
- astroid 用 `Uninferable`（值）表达"跟丢了"，griffe 用**类型化异常**表达解析失败/别名环——都是"失败是一等公民"，但都不是调用图语境的状态通道；
- scip-python 用类型检查器解析，不能解析的调用**静默缺失**（索引里没有 occurrence）。

**结论**：四态状态模型是我们要**自建**的契约，没有现成协议可借；可借的是"失败=一等值 / 类型化 / 显式跳过+计数"这组工程纪律（astroid、griffe、code2flow 各自给出证据）。

**误报 / 漏报取舍**（PyCG 系列论文给的量化窗口）：

| 工具        | 精度口径                      | 召回口径           | 取舍方向                  |
| --------- | ------------------------- | -------------- | --------------------- |
| PyCG      | precision ≈ 99.2%（宏基准）    | recall ≈ 69.9% | **precision 优先**，宁缺毋滥 |
| JARVIS    | 比 PyCG 高 84%              | 比 PyCG 高 20%   | 流敏感提升两端               |
| code2flow | 靠"跳过"保精度                  | 明显偏低（不追求）      | 可视化容忍缺失               |
| pyan3     | 误报模式明确（类名+`__init__` 双建边） | 漏报明显（无数值流）     | 两端都差                  |

对本项目的直接启示：步骤 5 完成门槛要求"**不把动态推测伪装成确定调用关系**"，与 PyCG 的 precision 优先同向；但我们要比 PyCG 多走一步——**把丢掉的 recall 显式化**（ambiguous / dynamic / unresolved 三类漏斗计数），使"未解析比例"可测量（完成门槛第 2 条），而不是像 PyCG/astroid 一样静默或仅日志化。

### 3.2 Parser Wrapper：astroid / griffe 如何包装 stdlib ast，哪些设计值得借鉴

**astroid 的包装形态**（"解析器 + 部分解释器"）：

- 接口与 stdlib ast 相似（`parse()` → Module；NodeNG 家族镜像 ast 节点），但叠加**推断层**：`node.infer()` 生成器产出"可能值"（可能多值！），特殊的 `Uninferable` 值表示无法推断——**不抛异常也不假装成功**；
- 含 `AstroidManager`（缓存/注册表）、inference transforms（可扩展推断）、`CallContext`（调用参数上下文）、类型化 `InferenceError` 家族；
- 对 C 扩展/常见库模式有大量内置补丁（"brain"）——这是它能推断 stdlib 的原因，也是重量来源。

**griffe 的包装形态**（"加载器 + 模型 + 别名 + 表达式"四件套）：

- `load()` 静态加载（不 import 目标代码）→ 模型树（Module/Class/Function/Attribute/**Alias**）；
- **Alias 是显式间接层**：跨模块引用 = Alias 链（target_path → resolve() → final_target），环用 `CyclicAliasError` 显式报错；
- 表达式用 `Expr` 包装（annotations/decorators/bases），配 `get_*` / `safe_get_*` 两档提取器（safe 失败返回 None）；
- 解析失败类型化（NameResolutionError / AliasResolutionError / UnimportableModuleError）。

**值得借鉴（无论是否引入依赖）**：

1. **失败是一等值**：解析结果用"值/状态"表达（astroid `Uninferable`、griffe 类型化异常），与我们 resolved/ambiguous/dynamic/unresolved 的四态设计同构——步骤 5 解析器内部应统一返回状态化结果，禁止用 None/异常混杂表达；
2. **间接层建模**：griffe 的 Alias 链 + 环检测直接对应我们"导入别名 → 模块属性 → 目标定义"的解析链与 import 环场景；
3. **两档提取器**：`get_*`（严格）与 `safe_*`（保守）分离，调用方按上下文选择；
4. **解析上下文参数化**：astroid `CallContext`（调用点的实参绑定）提示我们把"作用域链 + 调用点"作为解析输入的一部分显式建模。

**引入触发点（当前不引入）**：

- astroid：当语法级解析 + 自建局部解析的**未解析比例**在 Golden/狗粮上超出可接受阈值，且评审认定需要**类型推断/flow-sensitivity** 才能继续提升时，评估以"第二分析器后端"形式引入（LGPL-2.1 需评审；引入后必须通过确定性契约层过滤，见 §4 R4/B7）。
- griffe：当未来出现 API 表面/文档断链类需求时再评估（ISC 宽松，但功能域不同）。
- Parser Wrapper **端口抽象**本身：Development Plan 已明确"出现明确触发条件前不引入"——本文档只沉淀设计词汇（状态化结果、别名链、环、safe 模式），不预建抽象层。

### 3.3 图模型与遍历：节点/边数据结构、邻接索引、遍历算法如何组织

**调研对象的组织方式**：

| 项目 | 内部结构 | 输出/序列化 | 遍历算法 |
|------|----------|-------------|----------|
| PyCG | 赋值图 `Obj ↪ P(Obj)`（dict-of-sets）+ 作用域树 + 类层次（有序父类） | 邻接表 JSON（`{node: [callees]}`） | 全局不动点迭代（到状态收敛） |
| JARVIS | 每函数 FTG + CFG；按需生成 | JSON | 按需逐函数（demand-driven） |
| code2flow | groups（命名空间） + nodes（函数） | DOT / SVG | 子图抽取（upstream/downstream depth）、孤儿修剪 |
| SCIP | **明确反对**在索引内直接编码图（反对邻接表） | document/array + occurrence（流式友好） | 消费方自建索引 |
| rustworkx | Rust 图结构 + Python 绑定 | 内存对象 | SCC、拓扑、中心度等算法库 |

**对本仓库的立场**（结合 ADR-006/010）：

1. **序列化面**：不引邻接表作为持久形态——我们的 Artifact 是 `nodes + edges` 的规范排序元组（Pydantic 冻结模型），邻接索引是**分析器运行期的派生结构**（`dict[str, list[str]]`，按 kind 分桶），永不进序列化；这与 SCIP "索引格式不直接编码图"的判断一致，也避免同一事实两种表示。
2. **遍历算法**：步骤 5 需要的最小集是——邻接索引构建、（反）可达遍历（入口识别：找无调用者根节点 + 语法/配置入口标记）；均为标准库即可实现的确定性遍历（排序键、无 set 迭代序泄漏进输出）。SCC/拓扑等留到有真实查询需求时评审（rustworkx/NetworkX 触发点）。
3. **性能**：Development Plan 已冻结"图遍历性能优化在出现明确触发条件前不引入"；触发条件建议量化（步骤 6 实测）——例如自扫描/大型仓库的分析时间或内存超出阈值时，才评估算法库替换或增量分析。

### 3.4 与已冻结契约（ADR-010 / ADR-011）的冲突与不兼容点

**冲突清单**（按严重度排序；"提出方案"均只进入 ADR 草案，未实施）：

| # | 冲突点 | 现状（冻结契约） | 调研佐证 | 处理建议（待 Human 决策） |
|---|--------|------------------|----------|---------------------------|
| C1 | **CALLS 边无调用点证据** | `CodeEdge` 仅 `{id, kind, source_id, target_id}`，无 span；节点有 span，边没有 | PyCG 输出无 span；SCIP/DESIGN 强调"爆炸半径控制"（缺证据的边无法回溯） | `CodeEdge` 增可选 `source_span`，**kind=calls 时校验器强制必填**（"每次调用可回溯到源码行"）；`schema_version` 升级 |
| C2 | **无解析状态通道** | `CodeEdge` 无状态字段；完成门槛要求区分 resolved/ambiguous/dynamic/unresolved | 所有调研对象均无四态模型（§3.1）；astroid/griffe 证明"失败是一等值"可行 | `CodeEdge` 增可选 `resolution`（resolved / ambiguous），calls 边必填；dynamic/unresolved 不建边 |
| C3 | **统计口径是否容纳调用漏斗** | `ScanStats` 仅三个文件级漏斗计数（ADR-011："只存无法从图推导的计数"） | PyCG 只给图不给"丢了多少"（recall 缺口靠论文人工 gold 才发现）；code2flow 只告警 | 扩展 `ScanStats`：`calls_total/resolved/ambiguous/dynamic/unresolved`（属于"不可从图推导"的漏斗，符合 ADR-011 原则）；ScanResult 无 schema_version，属契约修订需显式批准 |
| C4 | **序列化破坏性变更流程** | ADR-010：`extra="forbid"`，新增字段对旧读取方即破坏性变更，须走 `schema_version` 升级流程 | SCIP 的版本演进（Protobuf 兼容规则）与 LSIF 教训（整数 ID 爆仓） | C1/C2 落地时 `CodeGraph.schema_version` 1 → 2；golden fixture、evaluator 基线按"新 Baseline 不覆盖 v1"纪律处理 |
| C5 | **错误码闭集** | `ScanErrorCode` 8 码闭集（ADR-011） | — | 调用不可解析**不是错误**（是分析事实），不新增错误码；若未来需要"警告级"通道（如动态调用提示）另行评审（ADR-011 复审触发已预留） |
| C6 | **确定性与集合序** | ADR-010：双跑字节相等、边去重、序列化排序 | PyCG 内部用 set 语义（可达集合），输出顺序依赖实现——不可直接移植 | 解析器内部允许 set 做工作记忆，但**出边前必须排序**（候选按 ID 排序、去重、自环跳过）；单测覆盖双跑字节相等 |
| C7 | **节点身份与重名** | 稳定 ID 含 kind + 重名 `#n` 后缀（ADR-010） | PyCG 邻接表 key 为裸限定名（不区分 kind/重名）——不可直接借用其 ID 方案 | 解析目标必须是**具体节点 ID**（含 `#n`）；`<locals>` 嵌套函数仅在同作用域内可解析，闭包逃逸视为 dynamic（边界登记） |
| C8 | **应用范围边界** | 步骤 4 的 IMPORTS 已是"仓库内解析，失败不建边" | JARVIS application-centered；PyCG 也会跟进可导入依赖（范围更大，成本更高） | CALLS 沿用：只解析仓库内目标；第三方/stdlib → unresolved（不建边、计数）；不跟进依赖内部（与 JARVIS E.A. 模式同向） |

## 4. 借鉴-否决清单

### 4.1 借鉴清单（借鉴点 → 落点 → 触发点）

| # | 借鉴点 | 落到哪个模块或契约 | 何时引入（触发点） | 来源 |
|---|--------|--------------------|--------------------|------|
| B1 | 命名空间感知的属性/方法解析（按定义位置区分同名成员） | 步骤 5 CALLS 解析器（`infrastructure/analyzers/`） | 实施时（步骤 5 开工即用） | PyCG §III-A |
| B2 | 类层次有序父类链 + MRO 方法解析 | 同上；Golden 增加 mro 类别用例 | 实施时 | PyCG §III-A；微基准 mro 7 例 |
| B3 | import 别名链建模（别名 → 目标对象） | 符号表设计（module attr → module → 定义） | 实施时 | PyCG import 规则；griffe Alias |
| B4 | 别名链**环检测**（显式错误而非静默） | 符号表设计（import 环、属性环） | 实施时 | griffe `CyclicAliasError` |
| B5 | 解析失败是一等值（状态化结果，两档提取器） | 解析器内部约定：禁止 None/异常混杂表达 | 实施时 | astroid `Uninferable`；griffe `safe_get_*` |
| B6 | "说不清就显式跳过 + 计数/告警"纪律 | 统计通道 + 测试断言（计数守恒） | 实施时（统计进契约需先过 §5 决策 3/4） | code2flow 跳过策略；PyCG recall 缺口教训 |
| B7 | 类型推断/流敏感作为**可选第二后端**的接口词汇（生成器式多值解析、调用上下文） | Parser Wrapper 端口设计**参考**（不预建） | 触发点：自建解析未解析比例超阈值且评审需要类型推断 | astroid `infer()`/`CallContext`；JARVIS FTG |
| B8 | 协议方法脱糖建边（with/for → `__enter__`/`__iter__` 等） | CALLS 解析器的调用点枚举（只影响"仓库内类定义的 dunder"可解析场景） | 实施时（低优先，Golden 覆盖后启用） | JARVIS Transfer rules |
| B9 | 孤儿/根节点分析 + 子图抽取参数 | 入口识别规则已先行落地（`analyzers/entry_points.py`）；剩余落点 = 根/孤儿分析与入口**表示层**设计；子图参数留步骤 8 | 表示层设计随 ADR-012 决策；子图参数留步骤 8 | code2flow orphan trimming / depth 参数 |
| B10 | 微基准分类清单（16 类 + 扩展类别）作为 CALLS Golden 检查表 | `eval/codegraph` 新增 CALLS cases 设计 | Golden 设计时（步骤 5 评测） | PyCG Table I；JARVIS 135 程序微基准 |
| B11 | precision/recall + 未解析比例 + 人工 gold 的评测方法论 | `eval/codegraph` 指标口径扩展；Baseline v2 新建不覆盖 | 步骤 5 评测时 | PyCG 宏基准方法（人工 gold 约 10h/项目）；eval/README 纪律 |
| B12 | SCIP 设计三原则（字符串 ID、避免图编码、爆炸半径控制） | ADR-012 引用佐证（无代码落点）；validator 强化参考 | ADR-012 落账时引用 | SCIP DESIGN.md |
| B13 | 应用中心范围（只解析应用内，依赖分析显式开关） | 范围决策（C8，ADR-012 确认） | 设计时 | JARVIS E.A./A.W. 模式 |
| B14 | 图算法库（rustworkx；备选 NetworkX） | 未来图查询/分析层（步骤 6+） | 触发点：实测规模/算法需求（SCC、拓扑、中心度） | rustworkx 文档；ADR-006 实测纪律 |

### 4.2 否决清单（否决项 + 原因 + 复审触发）

> ⚠️ 前提变更（2026-10-04）：本节否决判定基于「零依赖自研」前提；该前提已按 feedback 修订为 adoption-first——
> 选型以 [codegraph-oss-adoption.md](codegraph-oss-adoption.md) §3 为准，本节保留为研究期判断记录。

| # | 否决项 | 原因 | 复审触发 |
|---|--------|------|----------|
| R1 | 引入 PyCG 作为分析内核/依赖 | 已归档；may-call 无状态、无 span；ID 方案与 ADR-010 不兼容；绕过确定性契约层 | 无（归档项目；如需机制则自研实现） |
| R2 | 复用 JARVIS / jarviscg 代码 | **无许可证**（保留全部权利）；研究原型 | 上游补许可证且工程化后 |
| R3 | 复用 HeaderGen 代码/数据 | **无许可证**；Notebook+ML 库场景不匹配 | 上游补许可证且我们需要外部库类型存根时 |
| R4 | 即刻引入 astroid 依赖 | 重量级推断引擎；当前需求为语法级解析；LGPL 引入需评审 | 未解析比例超阈值且需类型推断（届时连同确定性过滤层一起评审） |
| R5 | 即刻引入 griffe 依赖 | 功能域不同（API 文档/断链），非调用图 | 出现 API 表面/文档断链需求时 |
| R6 | 采用 SCIP/Protobuf 作为产出格式 | 官方定位"传输格式非存储格式"；与 JSON Artifact 真源重复；引入编译链 | 出现跨工具互操作需求时——只做单向 exporter，不换真源 |
| R7 | 用 scip-python 作索引器 | Node16+/npm/pyright 全家桶；与零依赖纪律冲突 | 无（仅保留其"类型检查器级精度上限"作为决策证据） |
| R8 | 引入 LSIF | 已废弃并移除 | 无 |
| R9 | 引入 Sourcetrail | 已归档（2021）+ GPL-3.0 + GUI/DB 中心架构不符 | 无（UI 理念步骤 10 再参考） |
| R10 | 引入 pyan3 | GPL-2.0 传染性；分析浅（微基准两端皆低） | 无 |
| R11 | 引入 code2flow 作内核 | 启发式 + 同名方法跳过（方法级不可用）；无 span/状态 | 无（策略已借鉴） |
| R12 | 现在抽象 Parser Wrapper 接口层 | 无第二解析器触发点（Development Plan 明示）；过早抽象=为不存在的需求付成本 | 第二解析器（astroid/tree-sitter）真实立项时 |
| R13 | 现在引入 rustworkx/NetworkX 做邻接或遍历 | 规模未测量；违反"实测后决策"（ADR-002/006 精神） | 步骤 6 实测或图算法需求出现时 |
| R14 | 复刻 PyCG"全可达集合"边语义（无差别物化所有候选） | 与完成门槛"不把动态推测伪装成确定调用关系"冲突 | 无（替代方案=状态化边，见 §5） |
| R15 | 引入 tree-sitter（当前） | 无多语言/容错解析需求；CST→qualname 映射需重推导 | 多语言或错误容忍解析成为真实需求时 |

## 5. ADR 草案建议（供 Human 审核后落账 `docs/adr/`）

> 以下是**草案**：未经 Human 审核不得视为决策；建议落账文件名为
> `ADR-012-calls-resolution-discipline.md`（编号 012 当前空闲）。
> 落账时按 docs/adr/README.md 模板格式与状态流转（Proposed → Accepted）执行；
> 本节与 ADR 正文产生重复之前，以 ADR 为准（真源唯一原则）。
>
> ⚠️ 已修订（2026-10-04）：ADR-012 草案 v2（外部引擎 + 归一化纪律）见 [codegraph-oss-adoption.md](codegraph-oss-adoption.md) §6；
> 本节保留为历史版本（其契约部分仍被 v2 承接）。

### ADR-012（草案）：CALLS 解析纪律——状态化调用边、调用点证据与统计口径

- 状态：Proposed（草案 · 待 Human 审核）
- 日期：2026-10-03

**Context**

步骤 4 已冻结节点/边/序列化纪律（ADR-010）与扫描结果契约（ADR-011）；`EdgeKind.CALLS` 已存在但无实现与语义定义。调用关系比 DEFINES/IMPORTS 的模糊性更高（动态调用、鸭子类型、别名链），必须先规定"什么算确定调用、歧义如何表达、丢掉了什么如何计量"，否则会把推测伪装成事实（违反 Evidence First 与步骤 5 完成门槛），或让下游模块各自发明状态语义。前置调研（本文档）确认：PyCG/JARVIS 输出无状态区分的 may-call 集合；code2flow 跳过即丢失；astroid/griffe 将失败做成一等值但不是调用图语境——**没有现成契约可借，需自建**。

**Decision**

1. **状态化语义**：CALLS 边仅表达仓库内解析结论——`resolved`（唯一目标）与 `ambiguous`（2..N 个候选，按候选节点 ID 排序逐一建边）两种状态物化为边；`dynamic`（运行时决定）与 `unresolved`（第三方/stdlib/无法定位）**不物化边**。类实例化 `C(...)` 的边目标为可解析到的 `C.__init__`（含继承链；仓库内不可解析 → unresolved）。
2. **调用点证据**：`CodeEdge` 新增可选字段 `source_span`（SourceSpan）；校验器强制 **kind=calls 时必填**（每次调用可回溯文件+行号）；其他 kind 禁止携带。
3. **状态通道**：`CodeEdge` 新增可选字段 `resolution`（闭枚举 `resolved` / `ambiguous`）；kind=calls 时必填，其他 kind 禁止携带。
4. **统计漏斗**：`ScanStats` 扩展调用解析计数 `calls_total / calls_resolved / calls_ambiguous / calls_dynamic / calls_unresolved`（不可从图推导的漏斗，符合 ADR-011 统计口径原则）；不新增错误码（不可解析是分析事实而非错误）。
5. **范围**：只解析仓库内模块（application-centered，同 JARVIS E.A. 语义）；不跟进第三方/stdlib 内部。
6. **契约版本**：`CodeGraph.schema_version` 1 → 2（新增字段对 `extra="forbid"` 旧读取方是破坏性变更，按 ADR-010 §7 流程升版）；`ScanStats`/`ScanResult` 无 schema_version，其修订在本 ADR 内显式记录。
7. **确定性与去重**：沿用 ADR-010——候选排序、`(kind, source, target)` 去重、双跑字节相等；解析器内部允许 set 工作记忆，出边前必须排序。
8. **边界登记**：`<locals>` 嵌套函数仅同作用域可解析，闭包逃逸视为 dynamic；`getattr`/动态 import 视为 dynamic；`#n` 重名定义按作用域+行号解析到具体节点 ID；局部变量/实例变量的推断深度为实施设计项（`worker.run()` 类样例的定级随 Golden 实施冻结）。

**Alternatives**

- **无差别 may-call 边**（PyCG 语义）：与"不把动态推测伪装成确定调用关系"直接冲突；否决。
- **仅 resolved 出边、其余只进统计**（不出 ambiguous 边）：变更最小，但"歧义可查询"不可表达（API/UI 无法展示候选）；作为备选方案保留（Human 可降级选择）。
- **独立 CallResolutionReport 工件**：同一事实两个真源，违反 ADR-006/真源唯一；否决。
- **布尔 `resolved: bool`**：无法表达四态细分；否决。
- **状态明细放 ScanStats**：stats 定位为漏斗计数（ADR-011），明细进 stats 破坏其可推导性边界；否决。
- **不升 schema_version 直接加字段**：违反 ADR-010 兼容纪律；否决。
- **调用点证据放到独立"证据对象"层**：引入新概念层，且节点级 span 已确立同型先例（节点 span + hash）；否决（保持边/节点同构）。

**Consequences**

- 正向：调用事实与推测严格分离；每条 resolved/ambiguous 调用可回溯调用点行号；precision/recall/未解析比例可重复测量；步骤 6 持久化、步骤 8 API、步骤 10 UI 拿到统一状态语义。
- 负向：schema_version 2 → golden fixture 与 evaluator 基线需重建（Baseline v1 保留不覆盖，新增 v2）；旧读取方（若有）遇到新字段直接失败（有意为之）；ambiguous 边会放大边数量（候选 × 边），需与统计对照使用；`ScanStats` 修订无版本护栏，属显式契约变更。
- 复审触发：歧义边过多导致图噪声（考虑候选列表独立化）；需要"警告级"调用问题通道（与 ADR-011 复审触发合并考虑）；引入第二解析器或类型推断改变解析能力上限。

## 6. 证据索引（快照 2026-10-03）

| 对象 | 证据链接 |
|------|----------|
| PyCG 仓库 / 许可 / 归档 | https://github.com/vitsalis/PyCG （GitHub API：license=Apache-2.0；archived=true；pushed_at=2023-11-26） |
| PyCG 论文 | https://arxiv.org/abs/2103.00587 （ICSE'21；微基准 16 类别 = Table I；宏基准 precision/recall） |
| JARVIS 仓库 / 项目页 | https://github.com/pythonJaRvis/pythonJaRvis.github.io ；https://pythonjarvis.github.io/ （license=null；pushed_at=2026-03-22；项目页称投 TOSEM） |
| JARVIS 论文 | https://arxiv.org/abs/2305.05949 （v5 2024-09；135 微 / 6 宏基准；+67% 速度 / +84% 精度 / +20% 召回） |
| HeaderGen 仓库 | https://github.com/secure-software-engineering/HeaderGen （license=null；pushed_at=2025-01-30；SANER 2023；pycg_extended + typestub-database） |
| astroid 仓库 / 文档 | https://github.com/pylint-dev/astroid （LGPL-2.1；pushed_at=2026-09-30）；https://pylint.readthedocs.io/projects/astroid/en/latest/ （inference.html：`infer()`/`Uninferable`/扩展机制） |
| griffe 仓库 / 文档 | https://github.com/mkdocstrings/griffe （ISC；pushed_at=2026-10-02）；https://mkdocstrings.github.io/griffe/ （Alias/Expr/异常体系/加载器） |
| SCIP 协议 | https://github.com/scip-code/scip （Apache-2.0；DESIGN.md：传输格式非存储、避免图编码、避免整数 ID、爆炸半径） |
| scip-python | https://github.com/sourcegraph/scip-python （LICENSE.txt=MIT（pyright 派生）；Node16+；pyright 类型推断；环境自省） |
| LSIF 弃用 | https://lsif.dev/ （"no longer actively maintained … superseded by SCIP"）；SCIP DESIGN.md 脚注（"LSIF support has since been fully deprecated and removed"）；https://sourcegraph.com/blog/announcing-scip |
| Sourcetrail | https://github.com/CoatiSoftware/Sourcetrail （GPL-3.0；archived=true；pushed_at=2021-12-13；README 归档声明） |
| pyan3 | https://github.com/Technologicat/pyan （GPL-2.0；pushed_at=2026-09-21；PyCG 论文微基准对比数据） |
| code2flow | https://github.com/scottrogowski/code2flow （MIT；pushed_at=2025-07-27；README 算法 8 步 / 已知限制 / 子图参数） |
| tree-sitter | https://github.com/tree-sitter/tree-sitter （MIT；pushed_at=2026-10-02） |
| rustworkx | https://github.com/Qiskit/rustworkx （Apache-2.0；pushed_at=2026-09-28）；https://www.rustworkx.org/ （算法与发行形态） |

> 说明：许可证 / 归档 / 推送时间来自 GitHub API 快照（2026-10-03）；论文数字来自 arXiv 原文摘要与正文；机制描述来自官方 README / 文档 / 设计文档。上述外部链接为调研证据，非本仓库依赖。

## 7. 待 Human 决策点

1. **调研结论与文档落位**：本文档（`docs/codegraph/codegraph-calls-pre-research.md`）是否认可为步骤 5 前置调研交付物。
2. **ADR-012 落账**：§5 草案经修订后落账 `docs/adr/ADR-012-calls-resolution-discipline.md`（状态从 Proposed 开始）。
3. **契约变更三件套**（C1/C2/C3）：`CodeEdge.source_span` + `CodeEdge.resolution` + `ScanStats` 调用漏斗 + `schema_version` 1→2 —— 是否批准进入实施。
4. **ambiguous 策略**：物化歧义边（推荐）vs 仅统计不建边（备选，最小变更）。
5. **入口识别表示层**：识别规则已先行落地（`analyzers/entry_points.py`，main guard / FastAPI web_app）；待决策 = 产物表示（节点标记 / 新边类型 / 独立清单，建议并入 ADR-012）与入口种类扩展（CLI / `console_scripts` 等）。
6. **台账同步**：dev-log 登记与本地记忆回写（见本次任务收尾提案）。
