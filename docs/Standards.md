# InsightGraph

> 面向「洞察」的图谱化分析与可视化项目。

当前仓库处于初始化阶段：Phase 1 工程基础设施（AI 行为守则、CI、Docker Compose、
文档治理、评测骨架）已就位；后端 / 前端业务代码目录将在确定方案后按下面的约定逐步补齐。

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
├── docs/                          # 设计文档、架构说明、借鉴方案、ADR
│   ├── README.md                  # 文档索引与维护规则
│   ├── architecture.md            # 目标架构（草稿）
│   ├── Standards.md               # 本文档
│   ├── InsightGraph_Engineering Infrastructure.md
│   └── adr/                       # 架构决策记录
├── docker/
│   └── postgres/init.sql          # PostgreSQL 首次初始化脚本（扩展等）
├── eval/                          # 评测骨架（Baseline / Golden 规则）
├── scripts/                       # 本地质量检查脚本
│   ├── doc-link-check.sh          # 文档死链检查
│   └── ci-check.sh                # push 前全量检查
├── .githooks/                     # Git Hooks（需一次性安装，见快速开始）
├── .github/workflows/ci.yml       # CI（docs 立即可用；backend/frontend 自动启用）
├── docker-compose.yml             # PostgreSQL(pgvector) + Neo4j + Redis
├── .env.example                   # 环境变量模板
├── CLAUDE.md                      # AI 开发行为守则
├── .gitattributes / .gitignore
└── README.md / README_cn.md
```

> 业务代码目录（`backend/`、`frontend/`、`tests/`）在确定技术栈后创建，
> 避免留下空占位目录。

## 快速开始

```bash
# 1. 启动本地基础设施（PostgreSQL + Neo4j + Redis）
cp .env.example .env        # 可选：填写本地开发值（默认值开箱可用）
docker compose up -d

# 2. 本地质量检查（文档死链 + 代码门禁，后端/前端建立后自动启用对应检查）
bash scripts/ci-check.sh

# 3. 一次性安装 Git Hooks（pre-commit 死链检查 / pre-push 全量检查）
git config core.hooksPath .githooks
```

后端 / 前端建立后，本节将补充：运行时版本要求（Python 3.12 / Node 20）、
依赖安装命令、本地启动 / 调试命令、测试命令。

## 版本控制约定

- 分支模型：`main` 为可发布分支，功能开发走 `feat/<name>`，修复走 `fix/<name>`。
- 提交信息：`类型: 中文描述`（由 `.githooks/commit-msg` 强制校验），例如
  `feat: 新增依赖图导出`、`fix: 修正调用边漏解析`。
  类型白名单：feat / fix / refactor / chore / docs / test / style / perf / ci / revert；
  描述必须用中文，类型后不加括弧说明；主题行后可空行，再以 `- 文件/模块: 要点` 列改动明细。
- 提交流程：一个 commit 一个主题；提交前先给用户审核；仅提交本地，push 需明确指令。
- 提交前请确认 `git status` 中不包含密钥、个人配置或大型二进制文件。

## 首次推送

```bash
git remote -v                      # 确认 origin 指向本仓库
git push -u origin main            # 首次推送并建立上游跟踪
```

## 许可

尚未选定开源许可证；如需发布请补充 `LICENSE`。
