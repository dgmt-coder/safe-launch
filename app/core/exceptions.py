"""自定义异常层次 — 按分层组织."""

from __future__ import annotations


class AppException(Exception):
    """应用基础异常，所有业务异常由此派生."""


# --- Service 层 ---


class ServiceException(AppException):
    """Service 层通用异常."""


class DegradedException(ServiceException):
    """所有审核层均不可用，无法完成审核."""


# --- Module 层 ---


class ModuleException(AppException):
    """Module 层通用异常."""


class ExternalServiceException(ModuleException):
    """外部服务调用失败（DeepSeek、Qdrant、OpenAI 等）."""


# --- Repository 层 ---


class RepositoryException(AppException):
    """Repository 层通用异常."""


class NotFoundException(RepositoryException):
    """请求的资源不存在."""
