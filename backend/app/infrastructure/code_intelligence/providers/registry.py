"""调用图 Provider 注册表；组合根只按名称取实现，不直接依赖具体类。"""

from collections.abc import Callable
from pathlib import Path

from app.infrastructure.code_intelligence.providers.codegraph_ai import CodeGraphAIProvider
from app.infrastructure.code_intelligence.providers.engine_port import CallGraphProvider

ProviderFactory = Callable[[Path, int], CallGraphProvider]

_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "codegraph-ai": lambda path, timeout: CodeGraphAIProvider(path, timeout),
}


def create_call_graph_provider(name: str, executable: Path, timeout_seconds: int) -> CallGraphProvider:
    """从闭合注册表创建 Provider；未知名称显式失败。"""
    try:
        factory = _PROVIDER_FACTORIES[name]
    except KeyError as error:
        raise ValueError(f"未知调用图 Provider: {name}") from error
    return factory(executable, timeout_seconds)
