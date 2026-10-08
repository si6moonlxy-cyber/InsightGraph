"""外部引擎调用事实的解析状态映射。"""

from app.domain.codegraph.kinds import CallResolution


def engine_resolution() -> CallResolution:
    """POC 观察为零假阳性；引擎事实只作为 resolved 合并信号。"""
    return CallResolution.RESOLVED
