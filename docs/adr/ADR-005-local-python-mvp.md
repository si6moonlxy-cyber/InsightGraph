# ADR-005：MVP 先支持本地 Python 仓库

- 状态：Accepted
- 日期：2026-09-30

## Context

同时支持远程仓库和多种语言会把采集、鉴权、语法差异、符号解析和错误模型一起引入，难以建立可靠
基线。

## Decision

MVP 第一条闭环只接受本地 Python 仓库。首轮识别 Module、Class、Function、IMPORTS 和
DEFINES；CALLS、跨模块解析、远程 GitHub 和其他语言后续增加。

## Alternatives

- Python 与 TypeScript 同时支持：覆盖更广，但 Golden Dataset 与解析复杂度翻倍，拒绝。
- 先做远程 GitHub：产品展示更直接，但会掩盖核心分析问题，拒绝。

## Consequences

早期适用范围有限，但可以快速形成可重复、可精确评测的垂直闭环。基础节点评测稳定后复审语言与
仓库来源扩展。
