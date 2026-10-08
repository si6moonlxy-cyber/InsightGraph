"""外部调用图引擎的 infrastructure 内部端口。"""

from pathlib import Path
from typing import Protocol

from app.infrastructure.code_intelligence.models import ProviderStatus
from app.infrastructure.code_intelligence.raw_models.relation import RawCallGraph


class ProviderCallResult:
    """单次引擎查询结果；错误显式化，禁止异常/None 混合表达。"""

    def __init__(
        self,
        graph: RawCallGraph | None = None,
        *,
        error: str | None = None,
        invalid_records: int = 0,
    ) -> None:
        if (graph is None) == (error is None):
            raise ValueError("ProviderCallResult 必须且只能携带 graph 或 error")
        self.graph = graph
        self.error = error
        self.invalid_records = invalid_records


class CallGraphProvider(Protocol):
    """可替换的调用图 Provider 契约。"""

    name: str

    def probe(self, root: Path) -> ProviderStatus: ...

    def calls_for_symbol(self, root: Path, file_rel: str, line_1based: int) -> ProviderCallResult: ...
