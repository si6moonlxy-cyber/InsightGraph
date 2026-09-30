"""存活与就绪探针。"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """健康检查的稳定响应契约。"""

    status: Literal["ok", "ready"]


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    """只判断应用进程是否存活，不访问外部依赖。"""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    """骨架阶段尚无强制外部依赖，因此应用启动即就绪。"""
    return HealthResponse(status="ready")
