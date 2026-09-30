"""CodeGraph 持久化端口。"""

from typing import Protocol

from app.domain.codegraph.models import CodeGraph


class CodeGraphRepository(Protocol):
    """领域层只依赖此契约，不感知 JSON、PostgreSQL 或 Neo4j。"""

    async def save(self, graph: CodeGraph) -> None: ...

    async def get(self, repository_id: str, revision: str) -> CodeGraph | None: ...
