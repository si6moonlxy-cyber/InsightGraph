# ADR-003：LangGraph 只作为编排层

- 状态：Accepted
- 日期：2026-09-30

## Context

分析流程需要阶段状态、重试、暂停和恢复，但把 Collector、Analyzer 或 Reviewer 的核心逻辑直接写进
LangGraph 节点会导致能力无法脱离编排框架测试和复用。

## Decision

Collector、Analyzer、Validator、Reviewer、Reporter 先实现为独立应用服务。LangGraph 节点只接收
结构化状态、调用应用用例并返回结构化结果，不包含核心算法或直接数据库访问。

## Alternatives

- 所有逻辑直接写在节点中：开发初期快，长期测试和替换成本高，拒绝。
- 完全自研工作流引擎：当前没有必要，拒绝。

## Consequences

工作流代码更薄，能力可通过 API、CLI、测试或批处理复用；代价是必须先定义清晰的阶段契约。
