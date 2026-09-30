"""CodeGraph 的稳定中间表示。"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodeKind(StrEnum):
    """第一阶段支持的代码节点类型。"""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"


class EdgeKind(StrEnum):
    """代码结构关系；CALLS 在第二阶段实现。"""

    DEFINES = "defines"
    IMPORTS = "imports"
    CALLS = "calls"


class SourceSpan(BaseModel):
    """可回溯到源文件的准确范围。"""

    model_config = ConfigDict(frozen=True)

    file_path: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_line_order(self) -> "SourceSpan":
        if self.line_end < self.line_start:
            raise ValueError("line_end 不能小于 line_start")
        return self


class CodeNode(BaseModel):
    """稳定、确定性的 CodeGraph 节点。"""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    kind: NodeKind
    qualified_name: str = Field(min_length=1)
    language: str = Field(min_length=1)
    source: SourceSpan
    content_hash: str = Field(min_length=1)


class CodeEdge(BaseModel):
    """两个代码节点之间的有向结构关系。"""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    kind: EdgeKind
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)


class CodeGraph(BaseModel):
    """单次、单版本扫描产生的确定性代码图。"""

    repository_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    nodes: tuple[CodeNode, ...] = ()
    edges: tuple[CodeEdge, ...] = ()
