@echo off
rem ================================================================
rem  InsightGraph — 开发环境启动脚本（逐步加法构建）
rem ================================================================
rem  当前包含：[1] 开发日志（dev-log 分支）自动同步
rem            [2] Docker 环境检查与启动（引擎未运行则拉起 Docker Desktop 并等待就绪）
rem            [3] 基础设施容器启动（postgres + redis，幂等，等待 healthy）
rem            [4] 服务检验（容器状态 / pg_isready / redis PING / 宿主端口监听）
rem  后续按顺序逐步加入：[5] 依赖安装 [6] 后端 [7] 前端
rem
rem  设计原则：
rem    1. 每一步失败都不阻塞后续（日志拉不到 / Docker 未就绪，都不该挡住开发者看全貌）
rem    2. 只做当前阶段相关的事；未实现的段落用 [待加法] 标注
rem    3. 双击即可运行，结束后停留窗口显示结果
rem    4. 端口被占用时只报告并给出占用证据，不自动停止其他项目的容器
rem       （Docker 段落的结构参考 love-lobster 的 start.bat / fix-db-and-deps.bat 模式）
rem ================================================================
chcp 65001 >nul
setlocal enableextensions enabledelayedexpansion
title InsightGraph Start
cd /d "%~dp0"

echo ================================================================
echo   InsightGraph — 开发环境启动
echo ================================================================
echo.

rem ================================================================
rem Helper：检查端口占用（只报告证据，不做任何处理）
rem   用法：call :check_port 5432
rem ================================================================
goto :skipHelpers

:check_port
netstat -ano 2>nul | findstr /r /c:":%~1 " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [OK] 端口 %~1 空闲。
    goto :eof
)
echo   [警告] 端口 %~1 已被占用：
for /f "delims=" %%C in ('docker ps --filter "publish=%~1" --format "{{.Names}}" 2^>nul') do (
    echo       占用容器: %%C
)
for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| findstr /r /c:":%~1 " ^| findstr "LISTENING"') do (
    echo       宿主进程 PID %%A ^(可用 tasklist /FI "PID eq %%A" 查询进程名^)
)
goto :eof

:check_listen
netstat -ano 2>nul | findstr /r /c:":%~1 " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo     [X] 宿主端口 %~1 未监听。
) else (
    echo     [OK] 宿主端口 %~1 监听中。
)
goto :eof

:skipHelpers

rem ----------------------------------------------------------------
rem [1] 开发日志同步（dev-log 分支）
rem     首次运行：自动创建 .devlog 工作树（fetch + worktree add）
rem     之后每次：只拉取最新（不提交不推送；失败静默，不阻塞）
rem ----------------------------------------------------------------
echo [1] 开发日志同步...

if not exist ".git" (
    echo   [警告] 当前目录不是 Git 仓库（缺 .git），跳过开发日志同步。
    goto :after_devlog
)

set "BASH_EXE="
if exist "%ProgramFiles%\Git\bin\bash.exe" set "BASH_EXE=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH_EXE if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH_EXE=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH_EXE if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" set "BASH_EXE=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"

if not defined BASH_EXE (
    echo   [警告] 未找到 Git Bash（bash.exe），跳过开发日志同步。
    goto :after_devlog
)

where git >nul 2>nul
if errorlevel 1 (
    echo   [警告] 未找到 git，跳过开发日志同步。
    goto :after_devlog
)

if not exist ".devlog\devlog.sh" (
    echo   首次 Setup：创建 .devlog 工作树...
    git fetch origin dev-log || echo   [警告] fetch 失败，稍后可手动重试
    git worktree add .devlog dev-log || echo   [警告] worktree 创建失败，稍后可手动重试
)

rem 确保仓库级钩子生效（幂等；新克隆不会携带此配置）
git config core.hooksPath .githooks

if exist ".devlog\devlog.sh" (
    pushd ".devlog"
    "%BASH_EXE%" devlog.sh pull
    popd
)

:after_devlog
echo.

rem ----------------------------------------------------------------
rem [2] Docker 环境检查与启动
rem     ① docker CLI 存在性 ② 引擎探测 ③ 未运行则拉起 Docker Desktop 并轮询等待
rem ----------------------------------------------------------------
echo [2] Docker 环境检查...

set "DOCKER_READY=0"
where docker >nul 2>nul
if errorlevel 1 (
    echo   [X] 未找到 docker CLI。请先安装 Docker Desktop：
    echo       https://www.docker.com/products/docker-desktop/
    goto :after_docker
)

docker info >nul 2>&1
if not errorlevel 1 (
    echo   [OK] Docker 引擎运行中。
    set "DOCKER_READY=1"
    goto :after_docker
)

echo   [警告] Docker 引擎未运行，尝试启动 Docker Desktop...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
) else (
    start "" docker
)

echo   - 等待 Docker 引擎就绪（最长 180 秒）...
set /a DOCKER_TRIES=0
:wait_docker
docker info >nul 2>&1
if not errorlevel 1 (
    echo   [OK] Docker 引擎已就绪。
    set "DOCKER_READY=1"
    goto :after_docker
)
set /a DOCKER_TRIES+=1
if !DOCKER_TRIES! geq 180 (
    echo   [X] 等待超时。请手动打开 Docker Desktop，等待其显示 "Engine running" 后重跑本脚本。
    goto :after_docker
)
timeout /t 1 /nobreak >nul
goto :wait_docker

:after_docker
echo.

rem ----------------------------------------------------------------
rem [3] 基础设施容器启动（postgres + redis）
rem     幂等：已运行则跳过；端口被占用只报告证据，不自动处理
rem ----------------------------------------------------------------
echo [3] 基础设施容器启动（postgres + redis）...

if not "!DOCKER_READY!"=="1" (
    echo   [X] Docker 引擎未就绪，跳过容器启动。
    goto :after_containers
)

rem 幂等检测：两个容器均已 running 则跳过启动
set "PG_RUNNING=1"
set "REDIS_RUNNING=1"
docker inspect -f "{{.State.Status}}" insightgraph-postgres 2>nul | findstr /c:"running" >nul
if not errorlevel 1 set "PG_RUNNING=0"
docker inspect -f "{{.State.Status}}" insightgraph-redis 2>nul | findstr /c:"running" >nul
if not errorlevel 1 set "REDIS_RUNNING=0"

if "!PG_RUNNING!"=="0" if "!REDIS_RUNNING!"=="0" (
    echo   [OK] postgres 与 redis 均已在运行，跳过启动与端口预检。
    goto :after_containers
)

if "!PG_RUNNING!"=="0" (
    echo   [OK] postgres 容器已在运行。
) else (
    call :check_port 5432
)

if "!REDIS_RUNNING!"=="0" (
    echo   [OK] redis 容器已在运行。
) else (
    call :check_port 6379
)

echo   - 启动容器并等待 healthy（最长 90 秒）...
docker compose up -d --wait --wait-timeout 90 postgres redis
if errorlevel 1 (
    echo   [X] 容器启动失败。常见原因：
    echo       1^) 端口被其他项目或进程占用（见上方占用报告）
    echo       2^) Docker 引擎 / 镜像拉取异常
    echo       3^) 容器内配置错误（修复后重跑本脚本）
    echo   - 最近日志（postgres / redis）：
    docker compose logs --tail 20 postgres redis
) else (
    echo   [OK] 容器已启动并 healthy。
)

:after_containers
echo.

rem ----------------------------------------------------------------
rem [4] 服务检验（三重验证：容器状态 / 服务连通 / 宿主端口）
rem ----------------------------------------------------------------
echo [4] 服务检验...

if not "!DOCKER_READY!"=="1" (
    echo   [X] Docker 引擎未就绪，跳过服务检验。
    goto :after_verify
)

echo   - 容器状态：
docker compose ps --format "table {{.Name}}\t{{.Status}}"
echo.

echo   - PostgreSQL 连通（pg_isready）：
docker exec insightgraph-postgres pg_isready -U insightgraph -d insightgraph_dev >nul 2>&1
if errorlevel 1 (
    echo     [X] pg_isready 失败（容器未就绪或数据库未接受连接）
) else (
    echo     [OK] PostgreSQL 接受连接。
)

echo   - Redis 连通（redis-cli PING）：
set "REDIS_PING="
for /f "delims=" %%R in ('docker exec insightgraph-redis redis-cli ping 2^>nul') do set "REDIS_PING=%%R"
if /i "!REDIS_PING!"=="PONG" (
    echo     [OK] Redis 响应 PONG。
) else (
    echo     [X] Redis 未响应 PONG（实际返回：!REDIS_PING!）
)

echo   - 宿主端口监听：
call :check_listen 5432
call :check_listen 6379

echo.
echo   连接串（供后端 .env 使用）：
echo     DATABASE_URL=postgresql+asyncpg://insightgraph:insightgraph_dev@localhost:5432/insightgraph_dev
echo     REDIS_URL=redis://localhost:6379/0

:after_verify
echo.

rem ----------------------------------------------------------------
rem [待加法] 后续段落（按顺序逐步加入）：
rem   [5] 依赖安装（uv sync，缺失时安装）
rem   [6] 后端启动（uv run uvicorn ...）
rem   [7] 前端启动（pnpm dev）
rem ----------------------------------------------------------------
echo [待加法] 依赖安装 / 后端 / 前端启动 — 尚未接入。
echo.

echo ================================================================
echo   完成。
echo ================================================================
pause
