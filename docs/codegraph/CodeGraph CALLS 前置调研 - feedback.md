我核对了你这份《CodeGraph CALLS 前置调研》里的主要结论，并重新查了 PyCG、JARVIS、astroid、griffe、code2flow、SCIP/scip-python、tree-sitter、pyan3、rustworkx，以及与你当前目标最直接相关的 `codegraph-ai/CodeGraph`。

结论先说：

**这份文档作为“技术研究/架构设计参考”，可信度较高，我给 8.5/10；但作为你现在“快速借开源项目实现 CodeGraph 代码解析能力”的选型依据，我只能给 6/10。**

问题不在于它查错了，而在于它的决策倾向是：

> “研究这些项目 → 借鉴思想 → 自己实现分析器”

而你现在真正需要的是：

> “找到已经能跑的代码解析/调用图引擎 → 做 Adapter → 快速接入你自己的 CodeGraph Artifact / GraphRAG”。

这两个目标差别很大。

你上传的文档自身也明确把 PyCG、JARVIS、HeaderGen、code2flow 等多数项目定位成“机制借鉴、不直接引入”，并准备自建 `resolved / ambiguous / dynamic / unresolved` CALLS 契约。 codegraph-calls-pre-research 它甚至在否决清单里把 PyCG、scip-python、code2flow、tree-sitter 当前引入全部否掉。 codegraph-calls-pre-research

如果你的核心约束已经变成“**优先利用开源减少开发量**”，这部分需要重新决策。

---

## 一、文档中的核心事实，大部分是可靠的

我逐项核了几个最重要的。

PyCG 的判断基本准确。官方仓库已经在 2023 年 11 月归档，并明确表示没有继续开发计划；论文也确实报告约 **99.2% precision、69.9% recall、0.38 s/1k LoC**。[GitHub](https://github.com/vitsalis/PyCG/blob/main/README.md?utm_source=chatgpt.com)

所以文档里的：

> PyCG：机制值得参考，但不建议作为长期核心依赖

这个判断是合理的。 codegraph-calls-pre-research

但需要注意一个细节：**99.2% / 69.9% 是论文宏基准结果，不代表你的代码仓库也一定能达到这个数字。** Python 项目里的 DI、decorator、framework magic、monkey patch、runtime registration 都可能明显拉低实际 recall。

JARVIS 的论文数字也核对正确。论文摘要明确写的是，对比 PyCG 至少快 67%、precision 提升 84%、recall 至少提升 20%，并采用 function type graph、flow-sensitive intraprocedural analysis、strong update 和 on-the-fly 构图。[arXiv](https://arxiv.org/abs/2305.05949?utm_source=chatgpt.com)

所以它非常有研究价值，但由于许可和工程化问题，不适合作为你现在的“直接复制代码”对象。

astroid 的描述同样比较准确。它确实是 Pylint 使用的静态分析基础库，并提供扩展 AST、静态 inference 和 local scope。`NodeNG.infer()` 返回多个可能值，推断失败可以产生 `Uninferable`。[GitHub](https://github.com/pylint-dev/astroid?utm_source=chatgpt.com)

所以你文档提出：

> 不应该让解析函数只返回 `Node | None`，而应该把“解析失败/不确定”建模为一等状态

这个思想非常值得保留。

griffe 部分也可靠。它现在确实有明确的 `Alias`、`AliasResolutionError` 和 `CyclicAliasError`，并且 alias chain 会追踪到最终目标，环会被显式发现。[mkdocstrings](https://mkdocstrings.github.io/griffe/reference/api/?utm_source=chatgpt.com)

code2flow 部分也基本准确。它本身就把自己的定位说成：

> “pretty good estimate”

并明确指出动态语言无法完美生成调用图。它确实是 MIT，而且 README 说明 2021 重写前历史版本是 LGPL，重写后为 MIT。[GitHub](https://github.com/scottrogowski/code2flow?utm_source=chatgpt.com)

tree-sitter 的定位也准确：增量、容错、可以在语法不完整情况下继续生成 CST，而且是 MIT。[GitHub](https://github.com/tree-sitter/tree-sitter?utm_source=chatgpt.com)

所以从“资料是否胡编”这个角度说：

**没有发现系统性的虚构或明显错误。**

---

# 二、但这份调研漏掉了你现在最重要的候选：CodeGraph 本身

这是目前这份文档最大的参考价值缺口。

你当前项目本来就准备做：

> CodeGraph → 代码结构 → Call Graph → GraphRAG

而现在 `codegraph-ai/CodeGraph` 已经不是一个概念项目了。

它官方当前定位就是：

> semantic graph of codebase — functions, classes, imports, call chains

而且已经：

- 支持 **38 种语言**
- 基于 tree-sitter
- 有跨文件 import/call resolution
- 有 caller / callee / call graph / dependency graph / traversal
- 有 RocksDB 持久化
- 有增量索引
- 有 MCP Server
- Apache-2.0
- 可以从源码构建 [GitHub](https://github.com/codegraph-ai/CodeGraph?utm_source=chatgpt.com)

尤其是它已经直接提供：

`symbol_search`

`get_callers`

`get_callees`

`get_call_graph`

`get_dependency_graph`

`find_entry_points`

`traverse_graph`

`find_related_tests`

这些实际上已经覆盖了你自己步骤 5、步骤 6、步骤 8 里很大一部分计划。[GitHub](https://github.com/codegraph-ai/CodeGraph/blob/main/docs/tool-calling-guide.md?utm_source=chatgpt.com)

所以在你现在这个目标下，我认为：

**不应该先投入大量时间自己做 PyCG 式 CALLS engine。**

应该先回答另一个问题：

> CodeGraph 当前能力能不能覆盖我们 70%～90% 的解析需求？

如果能，就直接把它放在最下面做 Engine。

---

# 三、我建议你把架构方向从“自研解析器”改成“Adapter + OSS Engine”

我现在更推荐这样的结构：

```
GitHub Repo / Local Repo
        │
        ▼
┌─────────────────────────────┐
│ Open-source Analysis Engine │
│                             │
│ codegraph-ai/CodeGraph      │
│ tree-sitter                 │
│ optional: Pyright/Astroid   │
└──────────────┬──────────────┘
               │
        Normalize / Adapter
               │
               ▼
┌─────────────────────────────┐
│ Your CodeGraph Artifact     │
│                             │
│ CodeNode                    │
│ CodeEdge                    │
│ SourceSpan                  │
│ resolution                  │
│ evidence                    │
└──────────────┬──────────────┘
               │
        validate / enrich
               │
               ▼
        GraphRAG / API / UI
```

也就是说：

**第三方负责“看懂代码”。**

**你负责“统一语义、证据、契约、GraphRAG”。**

这是工程边界上非常重要的调整。

---

# 四、你现在最值得直接利用的项目，我会重新排这个优先级

|优先级|项目|我的建议|用途|
|---|---|---|---|
|S|`codegraph-ai/CodeGraph`|**先 POC，优先直接用**|symbols / imports / calls / graph traversal|
|S|tree-sitter|**保留底层能力**|多语言语法解析|
|A|Pyright / scip-python|**Python 精度增强器**|类型推断、definition resolution|
|A|astroid|**Python fallback**|inference / instance / MRO|
|B|griffe|借机制或局部使用|import / alias / API symbols|
|B|PyCG|借算法与 benchmark|CALLS 测试集、解析思路|
|B|code2flow|借 conservative strategy|ambiguous/unresolved 策略|
|C|JARVIS|论文参考|flow-sensitive / FTG|
|C|Joern|暂时别上|重型 CPG / data-flow / security|
|D|pyan3|不采用|GPL + 精度有限|

其中一个很重要的新判断是：

### scip-python / Pyright 不应该被这么早彻底否掉

你原文因为：

> Node + npm + Pyright 全家桶太重

就把 scip-python 基本排除了。 codegraph-calls-pre-research

从“零依赖、自研基础设施”的价值观来看没错。

但从：

> 快速做一个质量较高的 Python CodeGraph

来看，这个判断就未必对。

Pyright 当前仍是活跃的大型 Python 静态类型分析器，目标就是 large Python source base，MIT license。[GitHub](https://github.com/microsoft/pyright?utm_source=chatgpt.com)

它还已经解决了大量你如果自己做就会非常痛苦的问题：

import resolution、`.pyi`、PEP 561、generic、method type、inheritance、attribute inference 等。[GitHub](https://github.com/microsoft/pyright/blob/main/docs/type-stubs.md?utm_source=chatgpt.com)

所以：

**如果 CodeGraph 自身 Python call resolution 不够准，我会先考虑 Pyright/scip-python，而不是立刻自己重新实现 PyCG/JARVIS。**

---

# 五、这里有一个非常关键的现实判断

你现在不应该把问题定义成：

> “我要实现 CALLS。”

应该定义成：

> “我要为 GraphRAG 得到足够可信、可追溯的代码关系。”

这两者不同。

对于你的 InsightGraph / CodeGraph 场景，我认为真正需要的是：

```
FILE
MODULE
CLASS
FUNCTION
METHOD
IMPORT
CALL
CONTAINS
INHERITS
IMPLEMENTS
ENTRY_POINT
```

并且每个事实最好具有：

```
source_file
start_line
end_line
symbol
confidence / resolution
```

最终 GraphRAG 可以回答：

```
这个 API 从哪里进入？

→ router.py:41
→ UserService.create_user()
→ Repository.save()
→ SQLAlchemy session.commit()
```

这才是产品能力。

你没有必要证明：

> “这个 CALLS 算法完全是我自己实现的。”

---

# 六、你文档里有一部分我反而强烈建议保留

就是这套：

```
resolved
ambiguous
dynamic
unresolved
```

这个设计很好。

因为我查的这些项目里，确实没有哪个直接给你这一套完整语义。

你文档对此的总结是成立的。 codegraph-calls-pre-research

因此最佳结构反而应该是：

```
第三方 Engine
       ↓
Raw resolution result
       ↓
你自己的 Resolution Normalizer
       ↓
resolved
ambiguous
dynamic
unresolved
```

例如：

```
CallResolution(    caller="app.service.UserService.run",    callee="app.repo.UserRepository.save",    status="resolved",    source_span=...)
```

如果第三方只能给：

```
A → B
A → C
```

你 Adapter 再根据：

candidate count / provenance / heuristic

决定：

```
resolved
```

还是：

```
ambiguous
```

这样既吃到了开源能力，又保留了你自己的契约。

---

# 七、另外一个非常重要的现实：CodeGraph 自己也不是绝对真源

这一点不能因为它“正好叫 CodeGraph”就忽略。

它目前明显走的是：

```
tree-sitter
+
跨文件 symbol/import/call resolution
+
heuristics
```

而不是 Pyright/JARVIS 这种完整 Python 类型分析器。

官方说明它支持 cross-file import/call resolution，并能返回 callers/callees。[GitHub](https://github.com/codegraph-ai/CodeGraph/blob/main/vscode/README.md?utm_source=chatgpt.com)

因此我会把它定义为：

> **你的默认代码结构引擎**

而不是：

> **绝对正确的 CALLS oracle**

这也是为什么你的 `resolution` 契约还有价值。

---

# 八、如果是我现在负责你的项目，我会这样推进

第一阶段不要写复杂 CALLS analyzer。

先做一个非常小的 Spike：

```
fixtures/
  direct_call/
  import_alias/
  module_attr/
  class_method/
  inheritance/
  constructor/
  callback/
  decorator/
  getattr/
  dependency_injection/
```

每个 repo 大约 5～20 行代码。

然后跑：

```
codegraph-ai/CodeGraph
```

看看实际得到：

```
functions
classes
imports
calls
callers
callees
entry points
```

准确率。

如果：

```
80%+ Golden case
```

都够用：

直接集成。

如果 Python method / instance resolution 明显不足：

```
CodeGraph
   +
Pyright / astroid enrichment
```

如果只有极少部分缺：

```
CodeGraph
   +
自己实现 2~3 个 targeted resolver
```

而不是：

```
重新发明 PyCG
```

---

# 九、因此，我建议对你这份文档做一个重要改动

原来的核心结论大概是：

```
PyCG / JARVIS / astroid / griffe
        ↓
研究机制
        ↓
自研 CALLS resolver
```

我建议改成：

```
Level 1
codegraph-ai/CodeGraph
→ 直接集成验证

Level 2
Pyright / scip-python / astroid
→ 精度补强

Level 3
PyCG / JARVIS / griffe / code2flow
→ 算法和契约参考

Level 4
自研 resolver
→ 只补 OSS 无法覆盖的 gap
```

这更符合你现在说的：

**“借鉴和使用开源项目，快速开展 codeGraph 代码解析功能。”**

---

最终我的判断是：

**文档本身可信，可以继续保留作为研究资料，不建议推翻。**

但它现在更像一份：

> “CALLS 自研设计论证”

而不是：

> “CodeGraph OSS 快速落地选型”。

这两者应该拆开。

你文档中关于“Evidence First、source span、四态 resolution、Golden Cases、precision 优先”的思想很有价值；但“尽量不引第三方、先自己实现”这一层策略，我建议现在重新打开。

尤其是 `codegraph-ai/CodeGraph` 当前已经公开提供 Apache-2.0、38 语言、tree-sitter parsing、跨文件 import/call resolution、callers/callees/call graph/dependency graph、增量索引和 MCP，这与当前需求的重合度已经非常高。[GitHub](https://github.com/codegraph-ai/CodeGraph?utm_source=chatgpt.com)

**如果目标是快速出 MVP，我当前首选路线是：**

> `codegraph-ai/CodeGraph → Adapter → 你的 CodeGraph JSON Artifact → GraphRAG`

而不是：

> `stdlib ast → 自研 symbol table → 自研 resolver → 自研 call graph → GraphRAG`

前者明显更符合你现在的目标。