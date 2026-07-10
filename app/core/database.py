"""数据库引擎与会话工厂 — 基于 SQLAlchemy 2.0 异步模式."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config.settings import settings

# 模块级 engine（懒初始化，首次使用时创建）
_engine: Any = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    """懒加载创建异步引擎."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_POOL_OVERFLOW,
            echo=settings.DATABASE_ECHO,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """懒加载创建 session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖注入生成器.

    在 Litestar 中作为 Provide 的回调使用:
        dependencies={"db_session": Provide(get_db_session)}
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db_engine() -> None:
    """关闭数据库引擎（在应用 shutdown 时调用）."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
