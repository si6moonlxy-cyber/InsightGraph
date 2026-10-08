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


def test_codegraph_engine_defaults_to_disabled() -> None:
    settings = Settings()

    assert settings.codegraph_engine_enabled is False
    assert settings.codegraph_engine_path == ""
    assert settings.codegraph_engine_timeout_seconds == 30
    assert settings.codegraph_engine_total_budget_seconds == 900


def test_enabled_codegraph_engine_requires_path() -> None:
    with pytest.raises(ValidationError, match="CODEGRAPH_ENGINE_PATH"):
        Settings(codegraph_engine_enabled=True, codegraph_engine_path="")
