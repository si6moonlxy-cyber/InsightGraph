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

## 首批建议清单

| ADR | 主题 | 状态 |
|-----|------|------|
| ADR-001 | CodeGraph 与 GraphRAG 的职责边界 | 待撰写 |
| ADR-002 | PostgreSQL/pgvector 与 Neo4j 的存储分工 | 待撰写 |
| ADR-003 | LangGraph 作为分析编排层 | 待撰写 |
| ADR-004 | Evidence First 的报告生成约束 | 待撰写 |
| ADR-005 | 本地优先的仓库分析 | 待撰写 |

> 前四条的背景与取舍见
> [../InsightGraph_Engineering Infrastructure.md](../InsightGraph_Engineering%20Infrastructure.md) §7 / §17 / §21，
> 撰写时据此展开，不要复制粘贴——ADR 记录的是**当时的决策理由与代价**。
