# InsightGraph Backend

后端采用“领域核心 + 应用用例 + 基础设施适配器”的依赖倒置结构。

```text
api / workflows → application → domain ← infrastructure
```

`domain/` 不得依赖 FastAPI、数据库驱动、LangGraph 或 LLM SDK；外部技术通过领域或应用层定义的
`Protocol` 端口接入。完整边界见 [`../docs/architecture.md`](../docs/architecture.md)。

## 本地运行

```bash
uv sync --group dev
uv run uvicorn app.main:app --reload --port 4000
```

## 质量检查

```bash
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app tests
uv run pytest -m "not integration" -q
```
