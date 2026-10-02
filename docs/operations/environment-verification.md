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

> **本文不记录本机绝对路径。** 仓库内一律使用相对路径、占位符或标准环境变量形式
> （`%ProgramFiles%`、`%SystemRoot%` 等）。由 `scripts/abs-path-check.sh` 自动拦截。
> 具体盘符属于个人的机器信息，写在仓库里对他人无意义且会泄露目录结构。

---

## 2. 核验结果

**核验时间**：2026-10-02 · **分支**：`dev`

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
| 文档死链 | ✅ 全部可达 |
| 绝对路径检查 | ✅ 未发现机器特定路径 |
| 密钥扫描 | ✅ 未发现疑似硬编码密钥 |

> 直接运行 `uv run pytest -q` 为 46 passed；`ci-check` 排除了 1 个 integration 用例。

### 2.3 环境清单

| 项 | 状态 | 位置 / 版本 |
| --- | --- | --- |
| Docker Desktop | ✅ 已安装 | 程序位于**独立软件卷**（非系统卷，避免占用系统盘）；CLI 插件固定在 `%ProgramFiles%\Docker\cli-plugins`（Docker 强制，`--installation-dir` 不可覆盖） |
| Docker 引擎 | ✅ 运行中 | Client / Server **29.8.1**，OSType `linux` |
| Docker Compose | ✅ | v5.5.1 |
| WSL 数据根 | ✅ | 与 Docker 程序**同卷**（`--wsl-default-data-root`），WSL 平台默认版本 2 |
| docker-users 组 | ✅ | 当前用户已在组内 |
| Git Bash | ✅ | `%ProgramFiles%\Git\bin\bash.exe` |
| uv | ✅ | 0.11.7 |
| Node / pnpm | ✅ | Node 22 / pnpm 11 |

> ⚠️ 系统自带的 `%SystemRoot%\System32\bash.exe` 是 **WSL 启动器**，未安装发行版时执行会直接失败。
> 需要 shell 时请显式调用 Git Bash 的 `bash.exe`。

### 2.4 空间影响

| 项 | 占用 | 说明 |
| --- | --- | --- |
| Docker 程序本体 | 3366 MB | 静态，装在独立软件卷 |
| WSL 磁盘镜像 | 2444 MB | 随镜像 / 卷增长 |
| CLI 插件 | 675 MB | 固定在系统卷，无法迁移 |
| 容器镜像 | 689 MB | `pgvector/pgvector:pg16` 631 MB + `redis:7-alpine` 57.8 MB |

**装到哪一卷**：Docker 全套约 5.8 GB，后续还会叠加 Neo4j 镜像（约 600 MB ~ 1 GB）与
目标仓库快照（做代码分析时持续增长）。因此**不应装在容量紧张的工作卷上**——
本机最初装在只剩余约 6 GB 的工作卷，随即迁移到余量充裕的独立软件卷。

清理手段：`docker system prune -a`（删除未使用镜像）。

---

## 3. 核验中发现并已修正的文档偏差

| 位置 | 偏差 | 处理 |
| --- | --- | --- |
| `CLAUDE.md` §5.2 | 开发日志 worktree 硬编码了某一台机器的绝对路径 | 改为相对路径 `<仓库根>\.devlog`，并注明由 `start.bat` 首次运行自动创建 |
| `CLAUDE.md` §5.3 | 「postgres/redis 已在本机启动并 healthy」中的「本机」指向不明确 | 改为逐机器表述，并指向本文作为机器级证据 |
| `docs/Standards.md` | 「本地开发目录」写死了某一台机器的绝对路径 | 改为说明各开发者自定、不写入仓库 |
| `docs/InsightGraph_Engineering Infrastructure.md` | 引用参考仓库时写死了本机检出路径 | 改为通用表述 |
| 本文 | 初版写入了本机盘符与绝对路径 | 全面改为占位符与环境变量形式，并新增 `scripts/abs-path-check.sh` 自动拦截 |

---

## 4. 换机 / 新克隆后的核验清单

- [ ] `git config core.hooksPath .githooks`（新克隆不会携带此配置）
- [ ] 安装 Docker Desktop（Windows 家庭版走 WSL2 后端）：

      ```powershell
      # 管理员权限执行；把 <目标卷> 换成余量充裕的卷
      "Docker Desktop Installer.exe" install --quiet --accept-license `
        --installation-dir="<目标卷>:\Program Files\Docker" `
        --wsl-default-data-root="<目标卷>:\Program Files\DockerData"
      ```

      前置条件：目标卷必须是 **NTFS**（WSL2 的 vhdx 不支持 exFAT / FAT32）。
- [ ] 首次启动 Docker Desktop 并等待引擎就绪（会导入 WSL 发行版到数据根）
- [ ] `start.bat` → [1]~[4] 全绿（两容器 healthy，5432 / 6379 监听）
- [ ] `cd backend && uv sync && uv run pytest -q` 全绿
- [ ] `bash scripts/ci-check.sh` 全绿
- [ ] 把本次核验结果回写本文（更新日期与「核验结果」表）

> **注意**：安装 Docker 后，**已打开的终端不会自动刷新 PATH**。必须新开终端，
> 或直接双击 `start.bat`（资源管理器启动的 cmd 会读取最新环境变量）。

### 变更 Docker 安装位置的方法

Docker Desktop 的 Windows 服务与注册表项都记录了绝对路径，**手工搬目录会让
`com.docker.service` 失效**，`--installation-dir` 也只在安装时生效。因此换位置必须
**卸载后重装**：

1. `docker compose down` 停容器
2. `docker desktop stop`，再结束 `Docker Desktop` 进程
3. 用已安装目录下的 `Docker Desktop Installer.exe uninstall --quiet` 卸载（需提权）
4. **手工删除数据根残留**：卸载只注销 WSL 发行版，vhdx 文件会留在原数据根
5. 用新的 `--installation-dir` / `--wsl-default-data-root` 重装

容器与卷会在卸载时一并丢失，重装后需重新 `docker compose up -d`。仍在开发早期、
无持久化业务数据时执行本操作成本最低。

---

## 5. 未覆盖的内容

- **Neo4j 未核验**：`docker-compose.yml` 中已定义，但 `start.bat` 当前只拉起 postgres 与 redis。
  引入 GraphRAG 存储时需补充启动与检验段落，并更新 §4 清单。
- **真实 LLM 评测 workflow**：尚未建立（Phase 3），不在本文范围。
