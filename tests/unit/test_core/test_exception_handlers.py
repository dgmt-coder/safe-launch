"""统一异常处理器单元测试."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
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

from app.core.exception_handlers import (
    app_exception_handler,
    degraded_exception_handler,
    external_service_exception_handler,
    general_exception_handler,
    get_exception_handlers,
    http_exception_handler,
    internal_server_error_handler,
    not_authorized_handler,
    not_found_handler,
    service_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import (
    AppException,
    DegradedException,
    ExternalServiceException,
    NotFoundException,
    ServiceException,
)


def _make_request(path: str = "/test") -> MagicMock:
    """创建 mock Request."""
    req = MagicMock(spec=Request)
    req.url.path = path
    return req


class TestBusinessExceptionHandlers:
    """业务异常处理器."""

    def test_not_found_handler_returns_404(self):
        req = _make_request()
        exc = NotFoundException("记录不存在")
        resp = not_found_handler(req, exc)
        assert resp.status_code == HTTP_404_NOT_FOUND
        body = resp.decode_body() if callable(getattr(resp, "decode_body", None)) else resp.content
        assert isinstance(body, dict)
        assert body["code"] == "NOT_FOUND"

    def test_service_exception_handler_records_stack(self):
        req = _make_request("/api/v1/review")
        try:
            raise ServiceException("服务异常")
        except ServiceException as e:
            resp = service_exception_handler(req, e)
        assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    def test_degraded_exception_handler_returns_500(self):
        req = _make_request()
        exc = DegradedException("所有审核层不可用")
        resp = degraded_exception_handler(req, exc)
        assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    def test_external_service_exception_handler_returns_500(self):
        req = _make_request()
        exc = ExternalServiceException("DeepSeek API 超时")
        resp = external_service_exception_handler(req, exc)
        assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    def test_app_exception_handler_catches_base(self):
        req = _make_request()

        class CustomAppError(AppException):
            pass

        exc = CustomAppError("自定义错误")
        resp = app_exception_handler(req, exc)
        assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR


class TestHTTPExceptionHandlers:
    """HTTP / Litestar 异常处理器."""

    def test_http_exception_handler_passthrough_status(self):
        req = _make_request()
        exc = HTTPException(status_code=418)
        resp = http_exception_handler(req, exc)
        assert resp.status_code == 418

    def test_validation_exception_handler_returns_422(self):
        req = _make_request()
        exc = ValidationException(detail="content 字段不能为空", extra=[{"field": "content"}])
        resp = validation_exception_handler(req, exc)
        assert resp.status_code == HTTP_422_UNPROCESSABLE_ENTITY

    def test_internal_server_error_handler_returns_500(self):
        req = _make_request()
        exc = InternalServerException("内部错误")
        resp = internal_server_error_handler(req, exc)
        assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    def test_not_authorized_handler_returns_401(self):
        req = _make_request()
        exc = NotAuthorizedException("缺少 API Key")
        resp = not_authorized_handler(req, exc)
        assert resp.status_code == HTTP_401_UNAUTHORIZED


class TestGeneralExceptionHandler:
    """兜底异常处理器."""

    def test_general_handler_catches_runtime_error(self):
        req = _make_request()
        try:
            raise RuntimeError("意外错误")
        except RuntimeError as e:
            resp = general_exception_handler(req, e)
        assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR
        body = resp.decode_body() if callable(getattr(resp, "decode_body", None)) else resp.content
        assert body["code"] == "UNHANDLED_ERROR"

    def test_general_handler_catches_zero_division(self):
        req = _make_request()
        try:
            _ = 1 / 0
        except ZeroDivisionError as e:
            resp = general_exception_handler(req, e)
        assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    def test_general_handler_produces_no_stack_leak(self):
        """兜底处理器不应在响应中暴露堆栈信息."""
        req = _make_request()
        try:
            raise ValueError("secret_token=abc123")
        except ValueError as e:
            resp = general_exception_handler(req, e)
        body = resp.decode_body() if callable(getattr(resp, "decode_body", None)) else resp.content
        assert "secret_token" not in str(body["detail"])


class TestExceptionInheritance:
    """异常继承层次 — 子类异常处理器优先匹配."""

    def test_degredation_is_a_service_exception(self):
        """DegradedException 继承 ServiceException."""
        assert issubclass(DegradedException, ServiceException)
        assert issubclass(ServiceException, AppException)

    def test_not_found_is_app_exception(self):
        """NotFoundException 继承 AppException."""
        assert issubclass(NotFoundException, AppException)

    def test_external_service_is_app_exception(self):
        """ExternalServiceException 继承 AppException."""
        assert issubclass(ExternalServiceException, AppException)


class TestGetHandlers:
    """处理器映射测试."""

    def test_get_exception_handlers_returns_full_map(self):
        """应返回包含所有关键异常类型的映射."""
        handlers = get_exception_handlers()
        assert Exception in handlers
        assert AppException in handlers
        assert NotFoundException in handlers
        assert HTTPException in handlers
        assert InternalServerException in handlers
        assert len(handlers) >= 10

    def test_specific_exceptions_before_general(self):
        """子类异常处理器应在映射中（Litestar 按注册顺序匹配，需先注册子类）."""
        handlers = get_exception_handlers()
        keys = list(handlers.keys())
        # NotFoundException (子类) 应在 AppException (父类) 之前
        assert keys.index(NotFoundException) < keys.index(AppException)
        assert keys.index(DegradedException) < keys.index(ServiceException)
