"""CodeGraphAI 符号原始 DTO。"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RawLocation(BaseModel):
    """引擎位置；字段宽容读取，定位只信任路径与行号。"""

    model_config = ConfigDict(extra="ignore")

    file: str
    line: int = Field(ge=0)
    end_line: int | None = Field(default=None, ge=0)
    column: int | None = None
    end_column: int | None = None


class RawSymbol(BaseModel):
    """`codegraph_get_call_graph` 返回的扁平符号。"""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    path: str
    line_start: int = Field(ge=0)
    line_end: int = Field(ge=0)
    kind: str | None = None
    signature: str = ""
    col_start: int | None = None
    col_end: int | None = None

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return str(value)
