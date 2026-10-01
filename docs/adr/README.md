# ADR — 架构决策记录（Architecture Decision Records）

> 记录关键架构决策的上下文、结论与代价。
> 新增 ADR：在本目录新建 `ADR-XXX-短横线标题.md`，状态从 Proposed 开始。

---

## 模板

````markdown
# ADR-XXX: 标题

- 状态: Proposed | Accepted | Deprecated | Superseded by ADR-YYY
- 日期: YYYY-MM-DD

## Context

（面临什么问题？约束是什么？为什么现在必须决策？）

## Decision

（决定了什么？用完整的句子陈述。）

## Alternatives

（还考虑过哪些方案？为什么没选？各自的代价。）

## Consequences

（正向收益 / 负向代价 / 未来需要复审的触发条件。）
````

## 当前决策清单

| ADR | 主题 | 状态 |
|-----|------|------|
| [ADR-001](ADR-001-codegraph-graphrag-boundary.md) | CodeGraph 与 GraphRAG 的职责边界 | Accepted |
| [ADR-002](ADR-002-storage-responsibilities.md) | PostgreSQL/pgvector、Neo4j、Redis 与 Artifact 分工 | Proposed |
| [ADR-003](ADR-003-langgraph-orchestration-only.md) | LangGraph 只作为分析编排层 | Accepted |
| [ADR-004](ADR-004-evidence-first-claims.md) | Evidence First 的 Claim 约束 | Accepted |
| [ADR-005](ADR-005-local-python-mvp.md) | MVP 先支持本地 Python 仓库 | Accepted |
| [ADR-006](ADR-006-codegraph-json-artifact-first.md) | CodeGraph 第一阶段使用 JSON Artifact | Proposed |
| [ADR-007](ADR-007-datamodel-sqlalchemy-first.md) | 数据模型视图第一版从 SQLAlchemy 模型静态提取 | Proposed |
| [ADR-008](ADR-008-datamodel-independent-third-layer.md) | 数据模型视图作为独立第三语义层 | Proposed |
| [ADR-009](ADR-009-database-schema-normalization.md) | 数据库 Schema 推导与范式纪律 | Proposed |

> `Proposed` 决策需要真实数据或实现验证后转为 `Accepted`；不得因为代码暂时采用某种实现而自动
> 视为长期决策。
