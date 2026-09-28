# InsightGraph

> 面向「洞察」的图谱化分析与可视化项目。

当前仓库处于初始化阶段，仅包含项目骨架与版本控制配置。技术栈与目录结构将在
确定方案后按下面的约定逐步补齐。

---

## 仓库信息

| 项目 | 值 |
| --- | --- |
| 本地开发目录 | `D:\Code\InsightGraph` |
| 远程仓库 | `git@github.com:si6moonlxy-cyber/InsightGraph.git` |
| 默认分支 | `main` |
| 换行符规范 | 强制 LF（见 `.gitattributes`） |

## 目录结构

```text
InsightGraph/
├── docs/              # 设计文档、架构说明、调研笔记
│   └── architecture.md
├── .gitattributes     # 换行符与二进制文件规范
├── .gitignore         # 忽略规则（Node / Python / IDE / 系统文件）
└── README.md
```

> 业务代码目录（如 `src/`、`apps/`、`packages/`、`tests/`）在确定技术栈后创建，
> 避免留下空占位目录。

## 快速开始

仓库刚刚初始化，尚无构建脚本。确认技术栈后，本节将补充：

1. 环境要求（运行时版本、包管理器）
2. 安装依赖命令
3. 本地启动 / 调试命令
4. 测试与代码检查命令

## 版本控制约定

- 分支模型：`main` 为可发布分支，功能开发走 `feat/<name>`，修复走 `fix/<name>`。
- 提交信息：采用 Conventional Commits，例如
  `feat(graph): 支持节点拖拽布局`、`docs: 补充架构说明`。
- 提交前请确认 `git status` 中不包含密钥、个人配置或大型二进制文件。

## 首次推送

```bash
git remote -v                      # 确认 origin 指向本仓库
git push -u origin main            # 首次推送并建立上游跟踪
```

## 许可

尚未选定开源许可证；如需发布请补充 `LICENSE`。
