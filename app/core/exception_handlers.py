"""统一异常处理中间件 — 通过 ASGI middleware 捕获所有异常，记录堆栈，返回标准 JSON 响应."""

from __future__ import annotations

import json
import traceback
from typing import Any

import structlog
from litestar.status_codes import (
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from app.core.exceptions import (
    AppException,
    DegradedException,
    ExternalServiceException,
    NotFoundException,
    ServiceException,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# 异常类型 → HTTP 状态码 + 错误码
# 按 specificity 从高到低排列，优先匹配子类
# ---------------------------------------------------------------------------

_EXCEPTION_MAP: list[tuple[type[Exception], int, str]] = [
    # --- 业务异常 ---
    (NotFoundException,          HTTP_404_NOT_FOUND,               "NOT_FOUND"),
    (DegradedException,           HTTP_500_INTERNAL_SERVER_ERROR,   "DEGRADED"),
    (ExternalServiceException,    HTTP_500_INTERNAL_SERVER_ERROR,   "EXTERNAL_SERVICE_ERROR"),
    (ServiceException,            HTTP_500_INTERNAL_SERVER_ERROR,   "SERVICE_ERROR"),
    (AppException,                HTTP_500_INTERNAL_SERVER_ERROR,   "APP_ERROR"),
    # --- Litestar / HTTP ---
    # ValidationException / NotAuthorizedException / HTTPException
    # 这些由 Litestar 内置处理，middleware 不会拦到它们，保留映射以防万一
]


def _lookup(exc: Exception) -> tuple[int, str, str]:
    """根据异常类型返回 (status_code, error_code, detail)."""
    # 先尝试匹配已知业务异常
    for exc_type, status, code in _EXCEPTION_MAP:
        if isinstance(exc, exc_type):
            return status, code, str(exc)

    # 匹配 Litestar 内置异常（延迟导入，避免强制耦合）
    try:
        from litestar.exceptions import (
            HTTPException,
            NotAuthorizedException,
            ValidationException,
        )
    except ImportError:  # pragma: no cover
        pass
    else:
        if isinstance(exc, NotAuthorizedException):
            return HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", exc.detail
        if isinstance(exc, ValidationException):
            return HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", str(exc.detail)
        if isinstance(exc, HTTPException):
            return exc.status_code, "HTTP_ERROR", exc.detail

    # 兜底
    return HTTP_500_INTERNAL_SERVER_ERROR, "UNHANDLED_ERROR", "服务器内部错误"


def _format_traceback(exc: Exception) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def _log_exception(exc: Exception, path: str, status_code: int) -> None:
    """按严重级别记录日志."""
    if status_code >= 500:
        logger.error(
            "unhandled_exception",
            exception_type=type(exc).__name__,
            exception=str(exc),
            traceback=_format_traceback(exc),
            path=path,
            status_code=status_code,
        )
    else:
        logger.warning(
            "http_exception",
            exception_type=type(exc).__name__,
            exception=str(exc),
            path=path,
            status_code=status_code,
        )


class ExceptionHandlerMiddleware:
    """ASGI 中间件 — 统一捕获异常，记录堆栈，返回 JSON 错误响应.

    在 Litestar 中通过 ``DefineMiddleware`` 注册::

        DefineMiddleware(ExceptionHandlerMiddleware)
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            if scope["type"] != "http":
                raise

            path = scope.get("path", "")
            status_code, error_code, detail = _lookup(exc)
            _log_exception(exc, path, status_code)

            body = json.dumps(
                {"detail": detail, "code": error_code},
                ensure_ascii=False,
            ).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
