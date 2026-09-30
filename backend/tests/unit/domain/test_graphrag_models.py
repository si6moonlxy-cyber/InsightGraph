"""GraphRAG Claim 的 Evidence First 不变量测试。"""

import pytest
from pydantic import ValidationError

from app.domain.evidence import EvidenceStatus
from app.domain.graphrag import Claim


def test_supported_claim_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="Evidence"):
        Claim(
            id="claim:1",
            statement="项目使用 FastAPI",
            status=EvidenceStatus.SUPPORTED,
        )


def test_inference_can_exist_without_direct_evidence() -> None:
    claim = Claim(
        id="claim:2",
        statement="项目可能采用异步任务",
        status=EvidenceStatus.INFERENCE,
    )

    assert claim.evidence_ids == ()
