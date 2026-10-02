"""CodeGraph 的节点与边类型枚举。"""

from enum import StrEnum


class NodeKind(StrEnum):
    """第一阶段支持的代码节点类型；Repository 是图作用域，不是节点类型。"""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"


class EdgeKind(StrEnum):
    """代码结构关系；CALLS 在第二阶段实现。"""

    DEFINES = "defines"
    IMPORTS = "imports"
    CALLS = "calls"
