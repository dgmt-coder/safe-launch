"""统一异常处理中间件单元测试."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    ValidationException,
)

from app.core.exception_handlers import (
    ExceptionHandlerMiddleware,
    _format_traceback,
    _log_exception,
    _lookup,
)
from app.core.exceptions import (
    AppException,
    DegradedException,
    ExternalServiceException,
    NotFoundException,
    ServiceException,
)


def _http_scope(path: str = "/test") -> dict:
    return {"type": "http", "path": path, "method": "GET"}


def _ws_scope() -> dict:
    return {"type": "websocket", "path": "/ws"}


class TestLookup:
    """异常类型 → 状态码映射."""

    def test_not_found_maps_to_404(self):
        status, code, detail = _lookup(NotFoundException("记录不存在"))
        assert status == 404
        assert code == "NOT_FOUND"

    def test_degraded_maps_to_500(self):
        status, code, detail = _lookup(DegradedException("降级"))
        assert status == 500
        assert code == "DEGRADED"

    def test_external_service_maps_to_500(self):
        status, code, detail = _lookup(ExternalServiceException("API超时"))
        assert status == 500
        assert code == "EXTERNAL_SERVICE_ERROR"

    def test_service_maps_to_500(self):
        status, code, detail = _lookup(ServiceException("服务异常"))
        assert status == 500
        assert code == "SERVICE_ERROR"

    def test_app_exception_maps_to_500(self):
        class CustomError(AppException):
            pass
        status, code, detail = _lookup(CustomError("自定义"))
        assert status == 500
        assert code == "APP_ERROR"

    def test_validation_exception_maps_to_422(self):
        exc = ValidationException(detail="字段不能为空")
        status, code, detail = _lookup(exc)
        assert status == 422
        assert code == "VALIDATION_ERROR"

    def test_not_authorized_maps_to_401(self):
        exc = NotAuthorizedException("无权限")
        status, code, detail = _lookup(exc)
        assert status == 401
        assert code == "UNAUTHORIZED"

    def test_http_exception_passthrough_status(self):
        exc = HTTPException(status_code=418)
        status, code, detail = _lookup(exc)
        assert status == 418
        assert code == "HTTP_ERROR"

    def test_unknown_exception_maps_to_500(self):
        status, code, detail = _lookup(RuntimeError("意外"))
        assert status == 500
        assert code == "UNHANDLED_ERROR"
        assert detail == "服务器内部错误"

    def test_detail_does_not_leak_for_unknown(self):
        """未知异常的 detail 不暴露内部消息."""
        status, code, detail = _lookup(ValueError("secret_token=abc123"))
        assert detail == "服务器内部错误"
        assert "secret_token" not in detail

    def test_business_exception_detail_is_preserved(self):
        """业务异常的 detail 保留原消息."""
        status, code, detail = _lookup(NotFoundException("ID 123 不存在"))
        assert detail == "ID 123 不存在"


class TestMiddleware:
    """ExceptionHandlerMiddleware 测试."""

    @pytest.mark.asyncio
    async def test_passes_through_on_success(self):
        """无异常时中间件透传."""
        app = AsyncMock()
        middleware = ExceptionHandlerMiddleware(app)
        scope = _http_scope()
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)
        send.assert_not_called()

    @pytest.mark.asyncio
    async def test_catches_and_responds_on_exception(self):
        """异常时中间件拦截并返回 JSON 错误响应."""
        app = AsyncMock(side_effect=NotFoundException("X 不存在"))
        middleware = ExceptionHandlerMiddleware(app)
        scope = _http_scope()
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # 应发送了 http.response.start + http.response.body
        assert send.call_count == 2
        start_call = send.call_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 404

        body_call = send.call_args_list[1][0][0]
        data = json.loads(body_call["body"])
        assert data["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_re_raises_on_websocket(self):
        """WebSocket 异常直接向上抛."""
        app = AsyncMock(side_effect=RuntimeError("boom"))
        middleware = ExceptionHandlerMiddleware(app)
        scope = _ws_scope()
        receive = AsyncMock()
        send = AsyncMock()

        with pytest.raises(RuntimeError):
            await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_app_exception_returns_500_json(self):
        app = AsyncMock(side_effect=ServiceException("服务崩溃"))
        middleware = ExceptionHandlerMiddleware(app)
        scope = _http_scope("/api/v1/review")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        start_call = send.call_args_list[0][0][0]
        assert start_call["status"] == 500

        body_call = send.call_args_list[1][0][0]
        data = json.loads(body_call["body"])
        assert data["code"] == "SERVICE_ERROR"
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_content_type_header_is_json(self):
        app = AsyncMock(side_effect=Exception("boom"))
        middleware = ExceptionHandlerMiddleware(app)
        scope = _http_scope()
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        headers = {k.decode(): v.decode() for k, v in send.call_args_list[0][0][0]["headers"]}
        assert "application/json" in headers["content-type"]


class TestFormatTraceback:
    """堆栈格式化."""

    def test_format_includes_stack(self):
        try:
            raise ValueError("test error")
        except ValueError as e:
            tb = _format_traceback(e)
            assert "ValueError" in tb
            assert "test error" in tb
            assert "test_exception_handlers" in tb


class TestInheritance:
    """异常继承层次."""

    def test_degredation_is_service_exception(self):
        assert issubclass(DegradedException, ServiceException)

    def test_service_is_app_exception(self):
        assert issubclass(ServiceException, AppException)

    def test_not_found_is_app_exception(self):
        assert issubclass(NotFoundException, AppException)
