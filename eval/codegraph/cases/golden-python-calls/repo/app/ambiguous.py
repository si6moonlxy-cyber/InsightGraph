"""同模块重名定义：冻结 ambiguous 候选与 #n 节点口径。"""

if True:

    def choose() -> str:
        return "first"


def choose() -> str:
    return "second"


def use_ambiguous() -> str:
    return choose()
