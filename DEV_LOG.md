# 开发日志（当前任务）

> **编辑规则（必读）**
> - 只编辑自己名字对应的区块；不要改动别人的区块（跨区块改动会在同步时被覆盖）。
> - 只记录**当前进行中**的任务；完成或放弃后**直接删除该行**（历史一律看 `git log`）。
> - 条目格式：`- [yyyy-mm-dd] 一句话任务 @区域/模块`
> - 编辑后运行 `bash devlog.sh sync "<提交说明>"`（**说明必填**：一句话描述本次实际改动，如 `dlog: 回写 3 条 main 提交 @docs`；空话消息会被钩子拒绝。自动：格式校验 → 提交 → pull --rebase → push；被拒自动重试）。
> - 本分支已启用本地钩子：提交前自动校验格式、提交信息强制 `dlog:`、提交后自动推送（无需手动 push）。
> - 登记 / 完成：**向 AI 口述即可**——AI 代写 + 自动提交推送；`bash devlog.sh add/done` 是 AI 的内部命令，人不需要记。格式 / 日期 / 区块 / 颗粒度均由 AI 决定，人只做轻量 review。
> - 条目超过 **7 天**未更新会被 CI 提醒（仅提醒，不阻断）。
> - 本文件唯一真源在本分支（`dev-log`）；**不要**把日志副本放进 main / dev 分支。
>
> 网页直读：https://github.com/si6moonlxy-cyber/InsightGraph/blob/dev-log/DEV_LOG.md

## Sixmoonlxy（main）

- [2026-10-03] codegraph 产物不变量校验脚本（DEFINES 入边 / content_hash 重算 / imports 目标）+ CI 集成 @backend
- [2026-10-03] 步骤 4 Python AST 分析器（CodeGraph IR + 首个 Golden Dataset 与 evaluator） @backend
- [2026-10-03] 本地 Git Collector（确定性 SourceManifest + 采集 CLI） @backend
- [2026-10-02] start.bat 集成 docker/pgsql/redis 启动与检验 @infra
- [2026-10-02] docker 基础设施架子（postgres+redis 启动 / 修复 redis 空密码 bug） @infra
- [2026-10-02] domain 领域契约补全（稳定 ID / 扫描结果契约 / 确定性序列化） @backend
- [2026-10-01] 数据模型视图（第三类视图）架构决策：ADR-007 输入边界 / ADR-008 独立第三语义层 @docs
- [2026-10-01] 数据库 Schema 与范式纪律：ADR-009（访问模式反推 / 3NF 例外登记 / 三层记录） @docs
- [2026-10-01] 开发计划更新：datamodel 新步骤（步骤 7）+ 步骤 6 访问模式门槛 @docs
- [2026-09-30] 开发日志与协作体系（dev-log 独立分支 / 自动同步与回写 / start.bat） @协作流程
- [2026-09-30] 架构文档体系（系统架构真源 / 初始化思想导论 / ADR-001~006） @docs
- [2026-09-30] 后端分层架构骨架（Phase 2A：FastAPI + 领域契约 + 测试门禁） @backend
- [2026-09-29] 工程基础设施体系（AI 行为守则 / CI / Docker Compose / 质量门禁 / 评测骨架 / 文档治理） @infra
- [2026-09-28] 仓库初始化与 README 产品化（中英互跳） @项目

## Kalinka1962（dev）

