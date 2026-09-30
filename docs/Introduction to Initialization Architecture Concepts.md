# 初始化架构思想导论

> 最后更新：2026-09-30  
> 本文记录 InsightGraph 初始化架构背后的哲学。它解释“为什么这样分”，具体事实与接口以
> [系统架构](architecture.md)和代码为准。

## 1. 架构不是目录，而是允许发生的关系

整齐的文件夹不等于低耦合。真正的架构由三个问题决定：

1. 谁可以依赖谁？
2. 哪些事实属于这个领域？
3. 外部技术变化时，哪些核心代码不应该跟着变化？

InsightGraph 因此采用向内依赖：API、工作流和基础设施围绕应用与领域核心组织，而不是让领域模型
围绕 FastAPI、Neo4j 或 LangGraph 组织。

## 2. Evidence First：先证明，再解释

InsightGraph 不把“听起来合理”当成事实。项目能力判断必须沿证据链回到代码、文档和版本：

```text
Claim → Evidence → 文件/行号/文档出处 → 仓库 Revision
```

没有直接证据并不意味着禁止推理，而是必须诚实标记推理等级。`inference`、`hypothesis` 和
`unsupported` 不是失败状态，而是系统对知识边界的明确表达。

## 3. 两张图，而不是一张万能图

CodeGraph 和 GraphRAG 看起来都叫“图”，但它们描述的是不同世界：

- CodeGraph 的真值来自语法、符号和调用关系。
- GraphRAG 的真值来自概念、结论及其证据关系。

Function 不是 Technology，Class 也不是 Capability。强行合并会让每条边的语义越来越含糊，最终
无法判断查询结果究竟是代码事实还是模型推断。因此两张图保持边界，只通过稳定证据引用相连。

## 4. 领域核心必须比技术选型活得更久

FastAPI、Neo4j、Redis、LangGraph 和具体 LLM Provider 都可能变化。CodeGraph 的 Node、Edge、
SourceSpan，Evidence 的可信状态，以及 Claim 必须在这些技术替换后仍然成立。

领域层只定义模型、规则和端口：

```text
领域说：“我需要保存 CodeGraph。”
基础设施回答：“我用 JSON、PostgreSQL 或 Neo4j 实现。”
```

这就是依赖倒置：核心表达需求，外围实现需求。

## 5. 高内聚：每个模块只有一个变化理由

- 语法解析变化，只修改 Analyzer。
- 仓库读取方式变化，只修改 Collector。
- CodeGraph 语义变化，只修改 CodeGraph Domain。
- 证据可信规则变化，只修改 Evidence Domain。
- 数据库变化，只修改 Persistence Adapter。
- HTTP 协议变化，只修改 API。
- 工作流重试变化，只修改 Workflow。

如果一次技术替换需要同时修改 Router、领域模型、工作流和报告，说明边界已经失效。

## 6. 编排不是业务

LangGraph 适合表达阶段、状态、重试、暂停和恢复，但不应该成为算法的家。Collector、Analyzer、
Validator 和 Reporter 必须先是独立、可测试的普通 Python 能力；工作流只决定何时调用它们。

这样即使未来不用 LangGraph，核心能力仍能通过 CLI、API、测试或批处理直接运行。

## 7. 确定性优先于智能感

项目第一条闭环不使用 LLM：

```text
本地 Python 仓库 → AST → CodeGraph IR → JSON → Golden Dataset
```

原因不是排斥 AI，而是先建立一个可以精确测量的地基。结构事实稳定以后，LLM 才参与概念提取、
证据归纳和报告表达。确定性能力与概率性能力必须拥有不同评测方法和失败处理。

## 8. 端口先于存储

过早决定“所有图都进入 Neo4j”会让数据模型迎合数据库。第一阶段先以稳定 IR 和 JSON Artifact
观察真实数据规模、更新方式与查询需求，再决定最终存储。延迟决策不是逃避决策，而是在信息最充分
的时点决策。

## 9. 架构规则必须可以执行

“领域层不要依赖框架”如果只写在文档里，很快会失效。因此仓库使用架构测试扫描 import，CI 自动
阻止领域层依赖 FastAPI、SQLAlchemy、Neo4j、Redis、LangGraph 等外层技术。

重要边界应尽量变成：

- 类型约束；
- 测试断言；
- CI 门禁；
- 结构化 Schema；
- 可复现评测。

## 10. 架构向现实负责

架构文档只描述两种内容：当前真实存在的系统，以及明确标注的目标。目录不存在、服务未验证、能力
尚未实现时，不得写成“已经具备”。代码与文档冲突时，以代码为证据并立即修正文档。

## 11. 从 CoSense 学习，但不复制历史复杂度

本架构继承 CoSense 已验证的经验：Foundation 集中横切能力、能力域分层、统一 LLM Gateway、
Workflow 只做编排、Golden/Baseline 评测纪律。同时避免复制成熟产品长期演化形成的大量模块和兼容层。

InsightGraph 从小而清晰的领域核心开始，只有在真实需求出现时才增加适配器、数据库和工作流。

## 12. 最终判断标准

一个架构决策是否正确，不看它使用了多少流行技术，而看它是否让系统具备以下性质：

- 结论可追溯；
- 行为可复现；
- 模块可独立测试；
- 外部技术可替换；
- 失败边界清楚；
- 当前事实与目标状态不混淆。

这六点是 InsightGraph 初始化架构的长期判断尺度。
