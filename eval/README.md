# eval/ — InsightGraph 评测目录（骨架）

> 规则来源：[工程基础设施借鉴方案](../docs/InsightGraph_Engineering%20Infrastructure.md) §8–§12。
>
> 当前状态：CodeGraph evaluator 已进入 eval-v2，包含 `golden-python-basic` 与
> `golden-python-calls` 两个经人工复核的 Golden Dataset；检索与报告评测仍按能力落地时再建立。

---

## 目录约定

```text
eval/
├─ codegraph/          # CodeGraph 解析评测（Function / Class / Module / 边）
│  ├─ cases/           # 固定 Dataset（Golden Case，人工确认后冻结）
│  ├─ baselines/       # 基线 JSON（只创建，不自动覆盖）
│  └─ evaluator.py     # 评测入口（同 Dataset / Gold / Metric 可重复运行）
│
├─ retrieval/          # GraphRAG 检索评测（Hit@K / MRR / Evidence Recall）
│  ├─ cases/
│  ├─ baselines/
│  └─ evaluator.py
│
└─ report/             # Reporter 评测（Evidence Coverage Rate 等）
   ├─ cases/
   ├─ baselines/
   └─ evaluator.py
```

新增评测类别时遵循同一结构；**不要**为每个功能新开长期服务端口。

## Baseline 规则（硬性）

```text
1. Baseline 只创建，不自动覆盖。
   重写基线必须显式传参（--write-baseline），不允许默认行为改写基线。

2. 修改 Baseline：必须独立 Commit。
   修改 Golden：必须人工审核（AI 只能生成候选样本与预标注）。

3. PR 不允许因为当前实现失败而自动重写期望结果。

4. 一个能力一个基线文件，禁止把不同评测的 schema 混进同一个基线文件
   （CoSense 实测：混入会污染归一化读数）。

5. 数据集确需调整时：升版本，并用新版本重新计算旧实现的 Baseline。
```

CodeGraph eval-v2 固定比对节点、结构边、CALLS 的 resolution/span/truncation 与图级 entries；
`calls_dynamic`、`calls_unresolved` 和 `oversized_ambiguous_calls` 通过 AnalyzeOutcome 漏斗记录。
Baseline v2 使用 `golden-python-calls`，锚定 `python-ast/0.2` 实现提交 `b389760`；历史 v1 基线保留。

## 最小基线记录（JSON 字段）

```json
{
  "feature": "codegraph-parser",
  "dataset_version": "eval-v1",
  "git_sha": "<baseline commit>",
  "timestamp": "<ISO-8601>",
  "runner": "<command or evaluator>",
  "model_or_algorithm": "<version/config>",
  "metrics": { "primary": 0.0, "guardrail": 0.0 },
  "raw_outputs": "<artifact path>"
}
```

## 汇报格式（强制）

```text
Feature: <能力名称>
Dataset: <固定版本>
Baseline SHA: <commit>
Candidate SHA / working tree: <版本>

Primary
- <指标>: <before> → <after>（<delta>）

Guardrail
- <指标>: <before> → <after>（可接受/不可接受及原因）

Regression
- 新增失败：<case ids 或无>
- 已修复失败：<case ids 或无>
- 剩余风险：<说明>
```

缺少 Baseline 或 After Evaluation 时，结论只能写「实现完成，评测未完成」。

## 测量纪律（来自 CoSense 实测教训）

```text
1. 配对采样：多策略对比时，每轮内依次跑完所有泳道，分析逐轮配对差值。
2. 先预热：固定顺序串行对比前，先跑 1-2 轮预热并丢弃，
   否则第一个场景独吞冷启动成本，测出来的是执行顺序而不是性能差异。
3. 小样本不谈 P95：n < 100 时 P95 只是最大两三个值的插值，
   不要把它设成门禁；输出时必须标注样本量。
4. 消融臂设计：如 hop0_only / partial / full / full_no_gate 四臂，
   用 A vs C 证明能力增量，用 C vs D 证明门控在起作用。
5. 0 容忍断言：为每类确定性错误（编造引用 / 越权 / 过期数据）配
   ≥5 正例 + 5 反例，出现一条即失败。
```

## 与 CI 的关系

- 常驻 CI 不跑真实 LLM 评测（成本与波动）。
- 真实评测走独立手动触发 workflow（Phase 3 建立 `evaluation.yml`），
  运行 evaluator 后由门禁脚本与基线比对（tolerance 显式传入）。
- 评测产物（reports / snapshots）写入被 `.gitignore` 忽略的输出目录，
  长期保留的只有基线摘要与 Dataset。
