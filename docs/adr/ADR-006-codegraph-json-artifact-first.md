# ADR-006：CodeGraph 第一阶段使用 JSON Artifact

- 状态：Proposed
- 日期：2026-09-30

## Context

CodeGraph 的真实节点规模、增量更新方式和主要查询尚未得到测量。立即绑定数据库会让 IR 迎合未知的
物理模型。

## Decision

第一阶段通过 Pydantic Schema 生成稳定排序的 JSON Artifact，并由 `CodeGraphRepository` 端口隔离
存储。Artifact 同时服务于调试、Snapshot、Golden Dataset 和 Baseline。获得真实数据后再选择长期
存储。

## Alternatives

- 立即写入 Neo4j：图查询自然，但会过早固化 Schema。
- 立即写入 PostgreSQL：事务成熟，但同样缺少查询证据。
- 只保留内存对象：无法复现和对比，拒绝。

## Consequences

第一阶段查询能力有限，但输出可读、可 diff、可复现。出现 Artifact 过大、增量更新困难或查询性能
无法接受时，触发本 ADR 复审。
