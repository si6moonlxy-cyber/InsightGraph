# ADR-010：CodeGraph 契约纪律：稳定 ID、路径与哈希口径、确定性序列化

- 状态：Proposed
- 日期：2026-10-02

## Context

GraphRAG 与 datamodel 要通过稳定 ID 跨层引用 CodeGraph 节点（ADR-001 / ADR-008）；
Artifact 必须可读、可 diff、可复现（ADR-006）。但 ID 构造规则、重名处理、路径与
哈希口径、序列化形态均未定义，测试样例只给出过示意值。步骤 3/4 的 Collector 与
Python Analyzer 即将动工，为避免每个下游模块各自发明一套规则，必须先冻结契约。

## Decision

1. **节点 ID** = `{repository_id}:{kind}:{qualified_name}`，不含 revision；
   `repository_id` 不得包含 `:`。跨 commit 引用保持稳定，扫描作用域由
   `CodeGraph.repository_id + revision` 界定。
2. **重名规则**：同一 (kind, qualified_name) 出现多个定义（`@overload` 桩、条件分支）
   时，按 line_start 升序编号：首个保持裸名，第 2..N 个追加 `#2`..`#N`；编号由
   Analyzer 负责赋值，ID 构造器只做纯函数拼接与校验。
3. **边 ID** = `{kind}:{source_id}->{target_id}`；同一 (kind, source, target) 关系
   去重，只保留一条边。
4. **图模型边界**：NodeKind 只有 module / class / function；Repository 是图作用域，
   不是节点类型；`SourceSpan` 对所有节点保持必填。CodeGraph 校验：节点 ID 唯一、
   节点 ID 符合构造规则、边 ID 符合构造规则、边两端必须引用已存在的节点。
5. **路径口径**：一律仓库根相对 POSIX 路径（`/` 分隔、无 `./` 前缀、无尾斜杠），
   大小写保留；不做 Unicode 归一化（Git 按字节存储，同一提交跨平台 checkout 字节一致；
   NFC 归一化会在 macOS 上造成“存储路径 ≠ 磁盘文件名”的回读错位）。
6. **哈希口径**：算法 SHA-256，格式 `sha256:<64位小写hex>`；读取工作区内容并做
   CRLF→LF 归一后哈希（消除 autocrlf 平台差异）；文件级 `content_hash` 与节点级
   `content_hash`（= 该节点 source span 源码文本的哈希）分级，支持节点粒度的变更检测。
7. **序列化纪律**：规范 JSON = indent=2、字段声明顺序、Unicode 不转义、文件尾一个
   换行；`CodeGraph` 与 `SourceManifest` 携带 `schema_version`（int 主版本，仅破坏性
   结构变更 +1，与描述实现版本的 `parser_version` 相互独立）；领域契约统一
   `extra="forbid"`。
8. **稳定性测试三件套**：同一对象两次序列化字节相等、反序列化往返相等、golden fixture
   字节级回归（任何序列化变化必须是有意更新 fixture）。

## Alternatives

- **ID 含 revision**（如 `repo@abc:module:app.main`）：快照内精确，但每次 commit 后
  全部 ID 变化，跨层引用需额外血缘映射；否决。
- **内容哈希 ID**：天然唯一但不可读、不利 diff，任何编辑即变；与 ADR-006 的
  “可读可 diff” 目标相悖；否决。
- **重名全部编号 `#1..#N`**：更规整，但新重名出现时首个节点 ID 也会漂移；否决。
- **重名只留首个并将后续记为错误**：丢弃 `@overload` 桩等真实节点，违反
  “每个节点可回溯到源码”；否决。
- **ID 内嵌行号**：编辑导致 ID 漂移，跨 revision 追溯失效；否决。
- **新增 REPOSITORY 根节点**：`SourceSpan` 必填不变量出现例外；等有真实需求时再评审；
  否决。
- **统一 NFC 归一化**：macOS 上路径回读可能失败；“存储/原始双字段”超出 MVP 预算；
  否决。
- **读取 Git blob 零归一化**：未提交改动不可见、行号与编辑器不一致；且与步骤 3
  “记录文件消失、编码异常等局部错误”的工作区语义不符；否决。
- **工作区原始字节哈希**：autocrlf 配置差异破坏跨平台确定性；否决。
- **紧凑 JSON（含键排序变体）**：diff 粒度粗或需自定义排序逻辑；否决。

## Consequences

- 正向：跨层引用跨 commit 稳定；Artifact 字节级可复现、行级可 diff；契约违例
  在测试层立即失败（fail-fast）。
- 负向：删除或重排同名定义时 `#n` 后缀可能漂移（已知边界）；Unicode 一致性依赖
  Git 字节一致性而非归一化；`extra="forbid"` 使旧读取方遇到新增字段直接失败，
  必须伴随 schema_version 升级流程使用。
- 复审触发：实测出现跨平台 Unicode 路径差异；出现“精确指向某次扫描版本”的引用需求；
  Golden Dataset 暴露出重名规则不适用的真实案例。
