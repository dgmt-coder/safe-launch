"""Redis 客户端工厂 — 基于 redis.asyncio."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config.settings import settings

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """获取 Redis 客户端实例（懒加载）."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 连接（在应用 shutdown 时调用）."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
