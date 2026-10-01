# ADR-008：数据模型视图作为独立第三语义层

- 状态：Proposed
- 日期：2026-10-01

## Context

数据模型视图（ADR-007）是 CodeGraph 视图与 GraphRAG 证据视图之外的第三类分析产出。表、列、约束与
外键属于数据库语义，CodeGraph 描述的是程序结构语义：并入 CodeGraph 会让两边的语义边界与评测口径
互相污染；完全隔离、不允许任何引用，则丢失“这张表由哪段代码定义”的追溯价值。

## Decision

数据模型视图作为独立第三语义层实现：独立领域模块 `datamodel`，拥有独立 IR、端口、确定性 Artifact
与 Golden Dataset/评测口径；CodeGraph、GraphRAG 与 datamodel 在存储与评测上互不合并。

跨层引用只允许稳定 ID 的单向引用：datamodel 可以引用 CodeGraph 节点（如“表 → 定义它的 Class”），
CodeGraph 不得反向引用 datamodel；跨层 join 只发生在查询与展示层。该模式复刻 ADR-001 的
“可引用、不合并”。

## Alternatives

- 并入 CodeGraph 作为新节点/边类型：实现最省，但数据库语义侵入代码结构语义，Golden 指标与评测
  口径互相污染，拒绝。
- 作为 CodeGraph 的派生视图（不建独立 IR，前端二次推断）：省存储，但 relationship 参数、约束字符串
  等语义要在视图层重新解析源码，分析逻辑下放前端，拒绝。
- 三图合并为统一万能图：违反 ADR-001 红线，拒绝。

## Consequences

- 三个语义层各自维护 IR、Repository 与评测，模块与适配器数量增加；换来语义边界清晰、独立演进与
  可审计引用链。
- datamodel 的每个节点与每条边都必须能回溯到源码位置。
- GraphRAG 与 datamodel 之间的跨层引用不在本 ADR 范围，出现真实需求时另行决策。
