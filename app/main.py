"""Litestar 应用入口 — 工厂模式创建应用实例."""

from __future__ import annotations

from pathlib import Path

from litestar import Litestar
from litestar.di import Provide
from litestar.middleware.base import DefineMiddleware
from litestar.plugins.jinja import JinjaTemplateEngine
from litestar.template import TemplateConfig

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.health import HealthController
from app.api.controllers.history import HistoryController
from app.api.controllers.image_review import ImageReviewController
from app.api.controllers.rag import RagController
from app.api.controllers.text_review import TextReviewController
from app.core.config.settings import settings
from app.core.database import close_db_engine, get_db_session
from app.core.exception_handlers import (
    ExceptionHandlerMiddleware,
    create_exception_handlers,
)
from app.core.redis import close_redis
from app.services.review_service import ReviewService
from app.web.controllers.pages import PagesController


async def get_review_service(db_session: AsyncSession) -> ReviewService:
    """创建 ReviewService 依赖 — 注入数据库会话."""
    return ReviewService(db_session)


def create_app() -> Litestar:
    """创建 Litestar 应用实例 — 注册所有 Controller、依赖注入和异常处理器."""
    return Litestar(
        route_handlers=[
            PagesController,
            HealthController,
            TextReviewController,
            ImageReviewController,
            RagController,
            HistoryController,
        ],
        dependencies={
            "db_session": Provide(get_db_session),
            "review_service": Provide(get_review_service),
        },
        template_config=TemplateConfig(
            directory=Path(__file__).parent / "web" / "templates",
            engine=JinjaTemplateEngine,
        ),
        exception_handlers=create_exception_handlers(),
        middleware=[DefineMiddleware(ExceptionHandlerMiddleware)],
        on_startup=[_on_startup],
        on_shutdown=[_on_shutdown],
        debug=settings.DEBUG,
    )


async def _on_startup() -> None:
    """应用启动回调."""
    from app.core.logging import configure_logging

    configure_logging(debug=settings.DEBUG)

    import structlog
    logger = structlog.get_logger(__name__)
    logger.info(
        "safe-launch 启动中",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        debug=settings.DEBUG,
    )


async def _on_shutdown() -> None:
    """应用关闭回调 — 清理连接池."""
    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("safe-launch 正在关闭...")
    await close_db_engine()
    await close_redis()


app = create_app()


def run_server() -> None:
    """uv run server 入口 — 启动开发服务器."""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
