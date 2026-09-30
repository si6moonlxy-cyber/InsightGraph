"""配置 fail-fast 规则测试。"""

import pytest
from pydantic import ValidationError

from app.foundation.config import Settings


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        Settings(app_env="production", debug=True)


def test_cors_origins_are_normalized() -> None:
    settings = Settings(cors_origins="http://localhost:3000, http://localhost:3001")

    assert settings.cors_origin_list == [
        "http://localhost:3000",
        "http://localhost:3001",
    ]
