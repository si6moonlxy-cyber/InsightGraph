# ADR-011：扫描结果契约：单一 ScanResult、阶段 Outcome 与错误模型

- 状态：Proposed
- 日期：2026-10-02

## Context

扫描三个阶段（collect / analyze / persist）都可能出现成功、局部失败（单文件语法错误、
文件消失）与整体失败（路径无效、存储失败）。原端口 `collect() -> SourceManifest` /
`analyze() -> CodeGraph` 没有局部错误通道；Development Plan 要求“所有阶段都能用结构化
类型表达成功、局部失败和整体失败”。

## Decision

1. **单一 `ScanResult`**：`{repository_id, revision?, status, graph?, errors, stats}`。
   不变量由校验器强制：
   - `completed` = 有图 + 无错误 + 有 revision；
   - `partial` = 有图 + 至少一条 local 错误 + 无 fatal 错误 + 有 revision；
   - `failed` = 无图 + 至少一条 fatal 错误（revision 可为空）。
   - graph 携带时，其 `repository_id` / `revision` 必须与外层一致。
2. **阶段局部失败通道**：`CollectOutcome{manifest?, errors}` 与
   `AnalyzeOutcome{graph?, errors}`；`SourceManifest` 与 `CodeGraph` 保持纯事实。
   Outcome 校验器保证：错误必须属于本阶段；无 fatal 错误时必须产出清单/图
   （不允许静默失败）。
3. **错误模型**：`ScanError{stage, code, severity, message, file_path?}`；
   `severity ∈ {local, fatal}`；错误码为闭合集合（`path_invalid` / `git_error` /
   `file_unreadable` / `file_encoding` / `file_disappeared` / `symlink_rejected` /
   `syntax_error` / `storage_error`），新增码属于契约变更。
4. **统计口径**：`ScanStats` 只存无法从图推导的阶段漏斗计数
   （`files_collected / files_analyzed / files_failed`）；节点/边计数从 graph 现算；
   耗时等非确定值只进日志，不进确定性契约。
5. **persist 失败语义**：存储异常由编排器捕获，记录为 fatal `storage_error`，
   结果不携带图；重试与恢复语义留给步骤 8 的任务层，不在本契约内解决。

## Alternatives

- **判别联合**（`ScanCompleted | ScanPartial | ScanFailed` 三模型）：类型系统层面
  禁非法状态，但引入三套模型、联合序列化歧义与消费端分支；对 MVP 仪式感过重；否决。
- **逐阶段泛型包装 `StageResult[T]`**：信息量最大、阶段可独立表达，但泛型 +
  Pydantic 序列化稳定性需要额外测试，对单语言单实现过重；否决。
- **错误内嵌 `SourceManifest`**：Manifest 从“确定性文件清单”退化为“阶段报告”，
  且 Analyzer 侧没有对称通道（CodeGraph 不能携带错误）；否决。
- **端口返回裸 tuple**：破坏“跨层传递使用明确 Pydantic 契约”的纪律；否决。

## Consequences

- 正向：一个类型贯穿编排、序列化、未来的 API 与评测导出；非法状态在构造时立即失败；
  局部失败信息不丢失，图仍可产出与持久化。
- 负向：状态一致性依赖运行时校验器而非类型系统；`local` / `fatal` 标注正确性由
  各阶段实现方负责（评测与 Golden 测试需要覆盖）。
- 复审触发：需要 warning 级严重度、需要按阶段独立重试、或 API 层需要区分
  “可重试失败 / 不可重试失败”时。
