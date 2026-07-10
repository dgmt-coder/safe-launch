"""ReviewRecord 测试数据工厂."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.review_record import ReviewRecord
from app.schemas.review import ReviewCreate


def build_review_create(**overrides) -> ReviewCreate:
    """构建 ReviewCreate 测试数据."""
    defaults = {
        "content": "这是一段测试文本内容",
        "content_type": "text",
        "review_dimension": "legal",
    }
    defaults.update(overrides)
    return ReviewCreate(**defaults)


def build_review_record(**overrides) -> ReviewRecord:
    """构建 ReviewRecord ORM 对象（不写入数据库）."""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "content": "这是一段测试文本内容",
        "content_type": "text",
        "review_dimension": "legal",
        "status": "completed",
        "risk_level": "low",
        "review_result": {"is_violation": False},
        "degraded": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return ReviewRecord(**defaults)
