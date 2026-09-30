# ADR-004：Evidence First 结论约束

- 状态：Accepted
- 日期：2026-09-30

## Context

项目能力分析包含确定性事实和模型推断。如果不区分证据等级，用户无法判断结论是否可信，也无法从
报告回溯到源码或文档。

## Decision

所有 Claim 必须带 `supported`、`inference`、`hypothesis` 或 `unsupported` 状态。`supported`
必须至少引用一条 Evidence；Evidence 必须记录来源路径，并在适用时记录行号、仓库 revision 与
CodeGraph 节点 ID。

## Alternatives

- 只输出自然语言和引用：难以自动验证，拒绝。
- 没证据就不输出：会隐藏有价值但不确定的推理，拒绝。

## Consequences

报告生成和存储 Schema 更严格，但系统能够诚实表达知识边界，并建立 Evidence Coverage 等评测指标。
