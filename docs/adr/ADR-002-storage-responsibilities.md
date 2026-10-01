# ADR-002：存储职责分工

- 状态：Proposed
- 日期：2026-09-30

## Context

InsightGraph 同时需要事务元数据、向量检索、图关系、任务状态和可复现 Artifact。用单一存储承担所有
职责会扩大耦合，但过早确定 CodeGraph 的最终物理存储也缺少真实数据依据。

## Decision

暂定 **PostgreSQL** 保存 Repository、Scan、Job 与报告元数据，**pgvector** 保存证据向量，**Neo4j** 保存
GraphRAG 关系，**Redis** 保存短期 Job 状态与 checkpoint。**CodeGraph** 第一阶段使用 JSON Artifact，
最终存储延后决策。所有访问通过端口和适配器完成。

## Alternatives

- 全部进入 Neo4j：统一查询，但事务、向量和任务状态职责混杂。
- 全部进入 PostgreSQL：运维简单，但图遍历模型可能受限。
- 立即采用双图 Neo4j：缺少规模和查询证据，暂不接受。

## Consequences

初期适配器数量增加，但领域模型不绑定数据库。本 ADR 在获得真实 CodeGraph 规模、更新频率和查询
样本后复审并转为 Accepted 或被替代。
