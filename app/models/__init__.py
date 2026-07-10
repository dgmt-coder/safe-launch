"""SQLAlchemy ORM 模型聚合 — 所有模型在此导入以确保 Base.metadata 完整."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类."""
    pass


from app.models.review_record import ReviewRecord  # noqa: E402, F401

__all__ = ["Base", "ReviewRecord"]
