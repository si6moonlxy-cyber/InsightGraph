"""CodeGraphAI Raw DTO 到 Canonical CodeGraph 的适配组件。"""

from app.infrastructure.code_intelligence.adapter.canonicalize import merge_call_facts
from app.infrastructure.code_intelligence.adapter.identity import match_canonical_node

__all__ = ["match_canonical_node", "merge_call_facts"]
