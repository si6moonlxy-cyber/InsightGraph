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

**核验时间**：2026-10-02 · **仓库位置**：`D:\Code\InsightGraph` · **分支**：`dev`

### 2.1 `start.bat` — 四段全绿

| 段落 | 结果 | 事实 |
| --- | --- | --- |
| [1] 开发日志同步 | ✅ | `.devlog` 工作树就绪，`devlog.sh pull` 返回「已是最新」 |
| [2] Docker 环境检查 | ✅ | `Docker 引擎运行中` |
| [3] 基础设施容器启动 | ✅ | postgres 与 redis 已在运行（幂等跳过启动与端口预检） |
| [4] 服务检验 | ✅ | 两容器 healthy；`pg_isready` 通过；`redis-cli PING` 返回 PONG；宿主 5432 / 6379 均监听 |

连接串（脚本输出）：

```text
DATABASE_URL=postgresql+asyncpg://insightgraph:insightgraph_dev@localhost:5432/insightgraph_dev
REDIS_URL=redis://localhost:6379/0
```

### 2.2 后端质量门禁（在 `backend/` 下执行 `bash scripts/ci-check.sh`）

| 检查 | 结果 |
| --- | --- |
| Ruff | ✅ All checks passed |
| Ruff Format | ✅ 41 files already formatted |
| Mypy | ✅ Success: no issues found in 41 source files |
| Pytest（`-m "not integration"`） | ✅ 45 passed, 1 deselected |
| 文档死链 | ✅ 22 个文件全部可达 |
| 密钥扫描 | ✅ 未发现疑似硬编码密钥 |

> 直接运行 `uv run pytest -q` 为 46 passed；`ci-check` 排除了 1 个 integration 用例。

### 2.3 环境清单

| 项 | 状态 | 位置 / 版本 |
| --- | --- | --- |
| Docker Desktop | ✅ 已安装 | **程序 `D:\Docker`**（4.93.0 安装器）；CLI 插件在 `C:\Program Files\Docker\cli-plugins`（Docker 强制，`--installation-dir` 不可覆盖） |
| Docker 引擎 | ✅ 运行中 | Client / Server **29.8.1**，OSType `linux` |
| Docker Compose | ✅ | v5.5.1 |
| WSL 数据根 | ✅ | **`D:\DockerData`**（`--wsl-default-data-root`），WSL 平台默认版本 2 |
| docker-users 组 | ✅ | 当前用户已在组内 |
| Git Bash | ✅ | `C:\Program Files\Git\bin\bash.exe` |
| uv | ✅ | 0.11.7 |
| Node / pnpm | ✅ | Node 22 / pnpm 11 |

> ⚠️ 系统自带的 `C:\WINDOWS\system32\bash.exe` 是 **WSL 启动器**，未安装发行版时执行会直接失败。
> 需要 shell 时请显式调用 Git Bash 的 `bash.exe`。

### 2.4 磁盘预算

| 卷 | 核验前剩余 | 核验后剩余 | 说明 |
| --- | --- | --- | --- |
| C: | 38.5 GB | 39.9 GB | 只承担 CLI 插件（675 MB）；Docker 桌面端数据不在 C |
| **D:** | 11.6 GB | **5.9 GB** | 承担 `D:\Docker`（3366 MB）+ `D:\DockerData`（2444 MB）+ 镜像（689 MB）+ 卷（48 MB） |

**D 盘余量偏紧**，后续需注意：

- 目标仓库的快照会克隆到本地，做代码分析时占用会持续增长；
- 追加 Neo4j 镜像（`neo4j:5.26-community`）预计还需约 600 MB～1 GB；
- 清理手段：`docker system prune -a`（会删除未使用镜像）、或把
  `D:\DockerData` 迁到余量更大的卷（Docker Desktop → Settings → Resources → Disk image location）。

---

## 3. 核验中发现并已修正的文档偏差

| 位置 | 偏差 | 处理 |
| --- | --- | --- |
| `CLAUDE.md` §5.2 | 开发日志 worktree 硬编码为 `D:\Project_Mine\InsightGraph\.devlog`（另一台机器的路径） | 改为相对路径 `<仓库根>\.devlog`，并注明由 `start.bat` 首次运行自动创建 |
| `CLAUDE.md` §5.3 | 「postgres/redis 已在本机启动并 healthy（2026-10-02）」中的「本机」指向不明确 | 改为逐机器表述，并指向本文作为机器级证据 |

---

## 4. 换机 / 新克隆后的核验清单

- [ ] `git config core.hooksPath .githooks`（新克隆不会携带此配置）
- [ ] 安装 Docker Desktop（Windows 家庭版走 WSL2 后端）：
      `"Docker Desktop Installer.exe" install --quiet --accept-license --installation-dir=D:\Docker --wsl-default-data-root=D:\DockerData`
- [ ] 首次启动 Docker Desktop 并等待引擎就绪（会导入 WSL 发行版到数据根）
- [ ] `start.bat` → [1]~[4] 全绿（两容器 healthy，5432 / 6379 监听）
- [ ] `cd backend && uv sync && uv run pytest -q` 全绿
- [ ] `bash scripts/ci-check.sh` 全绿
- [ ] 把本次核验结果回写本文（更新日期与「核验结果」表）

> **注意**：安装 Docker 后，**已打开的终端不会自动刷新 PATH**。必须新开终端，
> 或直接双击 `start.bat`（资源管理器启动的 cmd 会读取最新环境变量）。

---

## 5. 未覆盖的内容

- **Neo4j 未核验**：`docker-compose.yml` 中已定义，但 `start.bat` 当前只拉起 postgres 与 redis。
  引入 GraphRAG 存储时需补充启动与检验段落，并更新 §4 清单。
- **真实 LLM 评测 workflow**：尚未建立（Phase 3），不在本文范围。
