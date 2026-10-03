"""本地仓库与远程仓库 Collector 的实现位置。"""

from app.infrastructure.collectors.git_repository import GitRepositoryCollector, resolve_repository_root

__all__ = ["GitRepositoryCollector", "resolve_repository_root"]
