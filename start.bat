@echo off
rem ================================================================
rem  InsightGraph — 开发环境启动脚本（逐步加法构建）
rem ================================================================
rem  当前包含：[1] 开发日志（dev-log 分支）自动同步
rem  后续按顺序逐步加入：[2] 依赖安装 [3] Docker [4] 后端 [5] 前端
rem
rem  设计原则：
rem    1. 每一步失败都不阻塞后续（日志拉不到，不该挡住开发）
rem    2. 只做当前阶段相关的事；未实现的段落用 [待加法] 标注
rem    3. 双击即可运行，结束后停留窗口显示结果
rem ================================================================
chcp 65001 >nul
setlocal enableextensions
title InsightGraph Start
cd /d "%~dp0"

echo ================================================================
echo   InsightGraph — 开发环境启动
echo ================================================================
echo.

rem ----------------------------------------------------------------
rem [1] 开发日志同步（dev-log 分支）
rem     首次运行：自动创建 .devlog 工作树（fetch + worktree add）
rem     之后每次：只拉取最新（不提交不推送；失败静默，不阻塞）
rem ----------------------------------------------------------------
echo [1] 开发日志同步...

if not exist ".git" (
    echo   [!] 当前目录不是 Git 仓库（缺 .git），跳过开发日志同步。
    goto :after_devlog
)

set "BASH_EXE="
if exist "%ProgramFiles%\Git\bin\bash.exe" set "BASH_EXE=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH_EXE if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH_EXE=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH_EXE if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" set "BASH_EXE=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"

if not defined BASH_EXE (
    echo   [!] 未找到 Git Bash（bash.exe），跳过开发日志同步。
    goto :after_devlog
)

where git >nul 2>nul
if errorlevel 1 (
    echo   [!] 未找到 git，跳过开发日志同步。
    goto :after_devlog
)

if not exist ".devlog\devlog.sh" (
    echo   首次 Setup：创建 .devlog 工作树...
    git fetch origin dev-log || echo   [!] fetch 失败，稍后可手动重试
    git worktree add .devlog dev-log || echo   [!] worktree 创建失败，稍后可手动重试
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
rem [待加法] 后续段落（按顺序逐步加入）：
rem   [2] 依赖安装（pnpm / uv，缺失时安装）
rem   [3] 基础设施：docker compose up -d（PostgreSQL / Neo4j / Redis）
rem   [4] 后端启动（uv run uvicorn ...）
rem   [5] 前端启动（pnpm dev）
rem ----------------------------------------------------------------
echo [待加法] 依赖安装 / Docker / 前后端启动 — 尚未接入。
echo.

echo ================================================================
echo   完成。
echo ================================================================
pause
