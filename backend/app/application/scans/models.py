"""扫描用例的输入和阶段间契约。"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ScanRequest(BaseModel):
    """第一阶段仅接收本地仓库路径和 Python 语言。"""

    model_config = ConfigDict(frozen=True)

    repository_id: str = Field(min_length=1)
    path: Path
    languages: tuple[str, ...] = ("python",)


class SourceFile(BaseModel):
    """Collector 产出的单个源文件事实。"""

    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)


class SourceManifest(BaseModel):
    """特定 Git revision 下的确定性文件清单。"""

    model_config = ConfigDict(frozen=True)

    repository_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    files: tuple[SourceFile, ...] = ()
