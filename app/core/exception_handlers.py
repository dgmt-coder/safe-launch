"""统一异常处理器 — 记录异常堆栈，返回标准错误响应."""

from __future__ import annotations

import logging
import traceback

from litestar import Request, Response
from litestar.exceptions import (
    HTTPException,
    InternalServerException,
    NotAuthorizedException,
    ValidationException,
)
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

logger = logging.getLogger(__name__)


def _format_exception(exc: Exception) -> str:
    """格式化异常堆栈为字符串."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


# --- 业务异常 ---

def not_found_handler(request: Request, exc: NotFoundException) -> Response:
    """资源不存在 — 404."""
    logger.warning(
        "资源不存在: %s | path=%s",
        exc,
        request.url.path,
        extra={"exception_type": type(exc).__name__},
    )
    return Response(
        content={"detail": str(exc), "code": "NOT_FOUND"},
        status_code=HTTP_404_NOT_FOUND,
        media_type="application/json",
    )


def service_exception_handler(request: Request, exc: ServiceException) -> Response:
    """Service 层异常 — 500."""
    logger.error(
        "服务异常: %s\n%s",
        exc,
        _format_exception(exc),
        extra={"exception_type": type(exc).__name__, "path": request.url.path},
    )
    return Response(
        content={"detail": str(exc), "code": "SERVICE_ERROR"},
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json",
    )


def degraded_exception_handler(request: Request, exc: DegradedException) -> Response:
    """降级异常 — 500."""
    logger.error(
        "审核降级失败: %s\n%s",
        exc,
        _format_exception(exc),
        extra={"exception_type": type(exc).__name__},
    )
    return Response(
        content={"detail": str(exc), "code": "DEGRADED"},
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json",
    )


def external_service_exception_handler(
    request: Request, exc: ExternalServiceException
) -> Response:
    """外部服务异常 — 500."""
    logger.error(
        "外部服务调用失败: %s\n%s",
        exc,
        _format_exception(exc),
        extra={"exception_type": type(exc).__name__, "path": request.url.path},
    )
    return Response(
        content={"detail": str(exc), "code": "EXTERNAL_SERVICE_ERROR"},
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json",
    )


def app_exception_handler(request: Request, exc: AppException) -> Response:
    """应用通用异常 — 500."""
    logger.error(
        "应用异常: %s\n%s",
        exc,
        _format_exception(exc),
        extra={"exception_type": type(exc).__name__, "path": request.url.path},
    )
    return Response(
        content={"detail": str(exc), "code": "APP_ERROR"},
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json",
    )


# --- Litestar / HTTP 异常 ---

def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """HTTP 异常（Litestar 内置）— 透传状态码."""
    logger.warning(
        "HTTP %s: %s | path=%s",
        exc.status_code,
        exc.detail,
        request.url.path,
        extra={"status_code": exc.status_code},
    )
    return Response(
        content={"detail": exc.detail, "code": "HTTP_ERROR"},
        status_code=exc.status_code,
        media_type="application/json",
    )


def validation_exception_handler(request: Request, exc: ValidationException) -> Response:
    """请求校验失败 — 422."""
    logger.warning(
        "参数校验失败: %s | path=%s",
        exc.detail,
        request.url.path,
        extra={"path": request.url.path},
    )
    return Response(
        content={"detail": str(exc.detail), "code": "VALIDATION_ERROR", "extra": exc.extra},
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        media_type="application/json",
    )


def internal_server_error_handler(
    request: Request, exc: InternalServerException
) -> Response:
    """内部服务器错误 — 500."""
    logger.error(
        "内部服务器错误: %s\n%s",
        exc,
        _format_exception(exc),
        extra={"exception_type": type(exc).__name__, "path": request.url.path},
    )
    return Response(
        content={"detail": "服务器内部错误", "code": "INTERNAL_ERROR"},
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json",
    )


def not_authorized_handler(request: Request, exc: NotAuthorizedException) -> Response:
    """未授权 — 401."""
    logger.warning(
        "未授权访问: %s | path=%s",
        exc.detail,
        request.url.path,
        extra={"path": request.url.path},
    )
    return Response(
        content={"detail": exc.detail, "code": "UNAUTHORIZED"},
        status_code=HTTP_401_UNAUTHORIZED,
        media_type="application/json",
    )


# --- 兜底异常 ---

def general_exception_handler(request: Request, exc: Exception) -> Response:
    """兜底 — 捕获所有未处理的异常，记录完整堆栈."""
    logger.error(
        "未处理异常: %s: %s\n%s",
        type(exc).__name__,
        exc,
        _format_exception(exc),
        extra={"exception_type": type(exc).__name__, "path": request.url.path},
    )
    return Response(
        content={"detail": "服务器内部错误", "code": "UNHANDLED_ERROR"},
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json",
    )


# --- 处理器映射 ---

def get_exception_handlers() -> dict:
    """返回异常处理器映射（按 specificity 从高到低排列）."""
    handlers = {
        # 业务异常
        NotFoundException: not_found_handler,
        DegradedException: degraded_exception_handler,
        ExternalServiceException: external_service_exception_handler,
        ServiceException: service_exception_handler,
        AppException: app_exception_handler,
        # HTTP / Litestar 异常
        NotAuthorizedException: not_authorized_handler,
        ValidationException: validation_exception_handler,
        InternalServerException: internal_server_error_handler,
        HTTPException: http_exception_handler,
        # 兜底
        Exception: general_exception_handler,
    }
    logger.info(
        "异常处理器就绪: %d 个 handler 已注册",
        len(handlers),
    )
    return handlers
