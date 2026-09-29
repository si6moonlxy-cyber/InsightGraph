# InsightGraph 文档索引

> 最后更新：2026-09-29 | 本文档是所有文档的入口

---

## 入口

| 文档 | 说明 |
|------|------|
| [../CLAUDE.md](../CLAUDE.md) | **行为守则**——Pre-Flight / 架构硬约束 / 编码规范 / 文档同步矩阵 / 快速参考 |
| [Standards.md](Standards.md) | 仓库信息、目录约定、版本控制约定 |
| [architecture.md](architecture.md) | 目标架构（草稿，技术栈确定后完善） |
| [InsightGraph_Engineering Infrastructure.md](InsightGraph_Engineering%20Infrastructure.md) | 工程基础设施借鉴方案（v2 · 证据版）——CI / Docker / 评测 / 文档治理全部细则 |

## 文档分类（新增文档必须进这些目录）

| 目录 | 放置内容 | 状态 |
|------|----------|------|
| [adr/](adr/README.md) | 架构决策记录（模板 + 首批清单） | ✅ 已建立 |
| `architecture/` | 系统真实状态、子系统设计（CodeGraph / GraphRAG / 工作流） | 需要时创建 |
| `engineering/` | 工程流程规范（评测驱动开发、视觉回归等） | 需要时创建 |
| `evaluation/` | 评测方法、指标口径 | 需要时创建 |
| `operations/` | 环境配置、排障、迁移 | 需要时创建 |

> 新建文档的准入：只有新模块设计、架构评审产出、决策记录三类允许。
> 临时调试 / 个人笔记不建文档（写进 commit message 或评测记录）。

## 文档维护规则（摘要）

- **真源唯一**：同一个事实只在一个文档维护，其它地方引用；发现重复 → 合并承接方。
- **命名纪律**：禁止 `-final` / `-v2` / `-new` 这类无法判断真源的命名；
  废弃文档加横幅标记（`> ⚠️ 已废弃，替代文档：…`）而不是删除。
- **死链零容忍**：相对链接必须可达，`scripts/doc-link-check.sh` 在 pre-commit 与 CI 中执行。
- **不写“待补充”**：要么写完整，要么删掉那一节；示例代码必须可运行。
- **同步矩阵**：代码变更 → 需要更新的文档，见 [CLAUDE.md](../CLAUDE.md) §四。
- **新鲜度检查**：文件头“最后更新”超过 90 天 → 顺手复核；声称的功能/路径必须在代码中真实存在。
