"""Provider 探测结果到稳定 provenance 的映射。"""

from app.domain.codegraph.models import ProviderRecord
from app.infrastructure.code_intelligence.models import ProviderStatus


def build_provider_record(name: str, status: ProviderStatus, tool_name: str) -> ProviderRecord | None:
    if not status.available or status.version is None:
        return None
    return ProviderRecord(
        name=name,
        version=status.version,
        asset_hash=status.asset_hash,
        tools_used=(tool_name,),
    )
