"""应用配置的唯一读取入口。"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """骨架阶段配置；外部适配器启用时再增加对应必填项。"""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "InsightGraph API"
    app_env: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    port: int = Field(default=4000, ge=1, le=65535)
    cors_origins: str = "http://localhost:3000"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    debug: bool = False
    codegraph_engine_enabled: bool = False
    codegraph_engine_path: str = ""
    codegraph_engine_timeout_seconds: int = Field(default=30, ge=1)
    codegraph_engine_total_budget_seconds: int = Field(default=900, ge=1)

    @model_validator(mode="after")
    def reject_production_debug(self) -> "Settings":
        if self.app_env == "production" and self.debug:
            raise ValueError("production 环境禁止开启 DEBUG")
        if self.codegraph_engine_enabled and not self.codegraph_engine_path.strip():
            raise ValueError("启用 CodeGraph 引擎时必须配置 CODEGRAPH_ENGINE_PATH")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔环境变量转换为中间件需要的列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """缓存已校验配置，测试可通过 cache_clear 隔离。"""
    return Settings()
