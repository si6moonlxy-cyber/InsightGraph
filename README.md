# InsightGraph

English | [简体中文](README_cn.md)

> Turn scattered information into an explorable graph — and extract reusable insights from it.

**Status: early stage of development.** The product has not been released yet.
This README describes the product idea and how it is meant to be used;
engineering documentation lives in [docs/](docs/README.md).

## The idea

InsightGraph exists to help you understand a software project — and to let you be sure that
what you understand is real.

Give it a repository. It reads the code and builds a structural map of how the project is
organized — its functions, classes, modules, imports and calls. It then builds a second map that
connects technical concepts and claimed capabilities back to the concrete evidence that supports
them: a file, a line, a document. What you get is an explorable map of what a project does,
and why you can believe it.

- **See the code as it is.** The structural map answers: *how is this codebase organized and called?*
- **Trust only what is evidenced.** Every claim that "the project does X" must point back to real
  evidence. Conclusions without direct evidence are explicitly marked as inference, hypothesis
  or unsupported — never presented as fact.
- **Explore, don't just answer.** Insights are organized as a graph you can navigate: every answer
  stays connected to its source, and one conclusion leads you to the next question.
- **Reproducible by design.** The same repository, version and configuration produce the same
  analysis, so findings can be reviewed, compared and revisited later.

## How to use it (planned)

```text
1. Point InsightGraph at a repository (local path or remote URL)
2. It analyzes the code structure and gathers document / code evidence
3. Browse the result as an interactive graph
4. Open any capability or conclusion and follow the evidence back to its source
5. Export a research report in which every key claim is traceable
```
