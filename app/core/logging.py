"""统一日志配置 — 基于 structlog 的结构化日志."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(*, debug: bool = False) -> None:
    """配置 structlog + 标准库 logging 集成.

    调用一次（通常在 app 启动时），对所有后续 ``structlog.get_logger()`` 生效.

    Args:
        debug: 开启 DEBUG 级别日志.
    """
    level = logging.DEBUG if debug else logging.INFO

    structlog.configure(
        processors=[
            # 添加日志级别
            structlog.stdlib.add_log_level,
            # 添加 logger 名称
            structlog.stdlib.add_logger_name,
            # 支持 logger.info("event", key=val) 风格
            structlog.stdlib.PositionalArgumentsFormatter(),
            # 格式化时间戳
            structlog.processors.TimeStamper(fmt="iso"),
            # 格式化异常堆栈（如果传入 exc_info）
            structlog.processors.format_exc_info,
            # 输出为 JSON 或彩色 Console
            _renderer(debug=debug),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 抑制第三方库的 DEBUG 日志
    _silence_noisy_libs(level=level)


def _renderer(*, debug: bool) -> structlog.typing.Processor:
    """根据环境选择渲染器：开发用彩色 Console，生产用 JSON."""
    if debug:
        # 彩色控制台输出，方便开发调试
        return structlog.dev.ConsoleRenderer(colors=True)
    return structlog.processors.JSONRenderer(ensure_ascii=False)


def _silence_noisy_libs(*, level: int) -> None:
    """抑制第三方库的 DEBUG 日志噪音."""
    for name in (
        "sqlalchemy.engine",
        "asyncio",
        "httpx",
        "httpcore",
        "qdrant_client",
        "uvicorn",
        "urllib3",
    ):
        logging.getLogger(name).setLevel(level)


def get_logger(*args: Any, **kwargs: Any) -> structlog.stdlib.BoundLogger:
    """获取 structlog logger（与 ``structlog.get_logger()`` 等价）."""
    return structlog.get_logger(*args, **kwargs)
