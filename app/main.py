"""Litestar 应用入口 — 工厂模式创建应用实例."""

from __future__ import annotations

from pathlib import Path

from litestar import Litestar
from litestar.di import Provide
from litestar.middleware.base import DefineMiddleware
from litestar.plugins.jinja import JinjaTemplateEngine
from litestar.template import TemplateConfig

from app.api.controllers.health import HealthController
from app.api.controllers.history import HistoryController
from app.api.controllers.image_review import ImageReviewController
from app.api.controllers.rag import RagController
from app.api.controllers.text_review import TextReviewController
from app.core.config.settings import settings
from app.core.database import close_db_engine, get_db_session
from app.core.exception_handlers import ExceptionHandlerMiddleware
from app.core.redis import close_redis
from app.web.controllers.pages import PagesController


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
        },
        template_config=TemplateConfig(
            directory=Path(__file__).parent / "web" / "templates",
            engine=JinjaTemplateEngine,
        ),
        exception_handlers={},
        middleware=[DefineMiddleware(ExceptionHandlerMiddleware)],
        on_startup=[_on_startup],
        on_shutdown=[_on_shutdown],
        debug=settings.DEBUG,
    )


async def _on_startup() -> None:
    """应用启动回调."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"safe-launch v{settings.APP_VERSION} 启动中 (env={settings.APP_ENV})")
    logger.info(f"Debug: {settings.DEBUG}")


async def _on_shutdown() -> None:
    """应用关闭回调 — 清理连接池."""
    import logging
    logger = logging.getLogger(__name__)
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
