# ADR-001：分离 CodeGraph 与 GraphRAG

- 状态：Accepted
- 日期：2026-09-30

## Context

代码结构事实与项目能力结论都适合用图表达，但节点、关系、真值来源和评测方式不同。混入同一套
无边界 Schema 会让语义失真，并使模型推断看起来像代码事实。

## Decision

CodeGraph 只描述 Module、Class、Function 及 DEFINES、IMPORTS、CALLS 等程序结构；GraphRAG
只描述 Technology、Concept、Capability、Claim 与 Evidence。GraphRAG 可用稳定 ID 引用
CodeGraph 节点，不能将代码节点直接等同于知识节点。

## Alternatives

- 单一万能图：查询方便，但类型和边语义会持续膨胀，拒绝。
- 完全隔离、不允许引用：边界清楚，但丢失证据追溯能力，拒绝。

## Consequences

两类图需要分别维护 Schema、Repository 与评测；换来明确真值边界、独立演进和可审计证据链。
