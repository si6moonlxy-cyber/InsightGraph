"""日志初始化。"""

import logging


def configure_logging(level: str) -> None:
    """使用标准库建立最小、可替换的日志配置。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
