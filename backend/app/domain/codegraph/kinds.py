"""CodeGraph 的节点与边类型枚举。"""

from enum import StrEnum


class NodeKind(StrEnum):
    """第一阶段支持的代码节点类型；Repository 是图作用域，不是节点类型。"""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"


class EdgeKind(StrEnum):
    """代码结构关系；CALLS 自 schema v2 起由步骤 5 实现。"""

    DEFINES = "defines"
    IMPORTS = "imports"
    CALLS = "calls"


class CallResolution(StrEnum):
    """调用边的静态解析状态；dynamic / unresolved 不会物化为边。"""

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    DYNAMIC = "dynamic"
    UNRESOLVED = "unresolved"


class EntryKind(StrEnum):
    """图级代码入口类型。"""

    MAIN_GUARD = "main_guard"
    WEB_APP = "web_app"
