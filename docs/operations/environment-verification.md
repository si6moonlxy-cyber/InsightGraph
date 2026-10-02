# 开发环境核验

> 最后更新：2026-10-02
>
> 记录在**具体开发机**上对 `start.bat` 与后端质量门禁的实际核验结果，作为
> [`CLAUDE.md`](../../CLAUDE.md) §5.3 状态地图中「环境已就绪」结论的机器级证据。

---

## 1. 为什么需要本文

`CLAUDE.md` §5.3 的状态地图是**逐机器**的：一台机器上验证通过，不代表另一台可用。
换机、新克隆或重装系统后，请按 §4 的清单重新核验，并把结果回写本文。

本文只记录**可复现的核验事实**；建设进度以 [`Development Plan.md`](../Development%20Plan.md) 为唯一真源。

---

## 2. 核验结果

**核验时间**：2026-10-02 · **仓库位置**：`D:\Code\InsightGraph` · **分支**：`dev`（= `main`）

### 2.1 `start.bat`

| 段落 | 结果 | 事实 |
| --- | --- | --- |
| [1] 开发日志同步 | ✅ 通过 | 首次运行自动创建 `.devlog` 工作树（tracking `origin/dev-log`）；`devlog.sh pull` 返回「已是最新」 |
| [2] Docker 环境检查 | ❌ 未通过 | `未找到 docker CLI` |
| [3] 基础设施容器启动 | ⏭ 跳过 | 依赖 [2] |
| [4] 服务检验 | ⏭ 跳过 | 依赖 [2] |

脚本按设计执行完毕：单段失败不阻塞后续，最后仍输出完整结论。

### 2.2 后端质量门禁（在 `backend/` 下执行）

| 命令 | 结果 |
| --- | --- |
| `uv sync` | ✅ 成功 |
| `uv run pytest -q` | ✅ **46 passed**，1 warning（Starlette `TestClient` 弃用提示，非本项目问题） |
| `uv run ruff check app/` | ✅ All checks passed |

### 2.3 环境缺口

| 项 | 状态 | 影响 |
| --- | --- | --- |
| Docker Desktop | ❌ 未安装（常见安装路径均无痕迹） | `start.bat` [2][3][4] 无法执行；Development Plan 步骤 6（持久化）在本机无法端到端验证 |
| WSL 发行版 | ❌ 无 | Docker Desktop 的常见后端依赖 |
| Git Bash | ✅ `C:\Program Files\Git\bin\bash.exe` | `scripts/*.sh`、`.githooks/*` 可用 |
| uv | ✅ 0.11.7 | 后端依赖安装与测试可用 |
| Node / pnpm | ✅ Node 22 / pnpm 11 | Phase 3 前端可用 |

> ⚠️ 系统自带的 `C:\WINDOWS\system32\bash.exe` 是 **WSL 启动器**，未安装发行版时执行会直接失败。
> 需要 shell 时请显式调用 Git Bash 的 `bash.exe`。

---

## 3. 核验中发现并已修正的文档偏差

| 位置 | 偏差 | 处理 |
| --- | --- | --- |
| `CLAUDE.md` §5.2 | 开发日志 worktree 硬编码为 `D:\Project_Mine\InsightGraph\.devlog`（另一台机器的路径） | 改为相对路径 `<仓库根>\.devlog`，并注明由 `start.bat` 首次运行自动创建 |
| `CLAUDE.md` §5.3 | 「postgres/redis 已在本机启动并 healthy（2026-10-02）」中的「本机」指向不明确 | 改为逐机器表述，并指向本文作为机器级证据 |

---

## 4. 换机 / 新克隆后的核验清单

- [ ] `git config core.hooksPath .githooks`（新克隆不会携带此配置）
- [ ] `start.bat` → [1] 开发日志同步通过（`.devlog` 工作树创建成功）
- [ ] 安装 Docker Desktop 后重跑 `start.bat` → [2][3][4] 通过：
      postgres、redis 容器 healthy；宿主 5432 / 6379 处于监听；`pg_isready` 与 `redis-cli PING` 均成功
- [ ] `cd backend && uv sync && uv run pytest -q` 全绿
- [ ] `bash scripts/ci-check.sh` 全绿
- [ ] 把本次核验结果回写本文（更新日期与「核验结果」表）

---

## 5. 未覆盖的内容

- **Neo4j 未核验**：`docker-compose.yml` 中已定义，但 `start.bat` 当前只拉起 postgres 与 redis。
  引入 GraphRAG 存储时需补充启动与检验段落，并更新 §4 清单。
- **真实 LLM 评测 workflow**：尚未建立（Phase 3），不在本文范围。
