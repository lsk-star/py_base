from http import HTTPStatus
from typing import Any

from app.core.errors import ErrorCode


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = HTTPStatus.BAD_REQUEST,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在", *, details: Any = None) -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, status_code=HTTPStatus.NOT_FOUND, details=details)


class ConflictError(AppError):
    def __init__(self, message: str = "资源冲突", *, details: Any = None) -> None:
        super().__init__(ErrorCode.CONFLICT, message, status_code=HTTPStatus.CONFLICT, details=details)


class DependencyUnavailableError(AppError):
    def __init__(self, message: str = "依赖服务暂不可用", *, details: Any = None) -> None:
        super().__init__(
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            message,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            details=details,
        )


class ConfigurationError(RuntimeError):
    """启用的能力缺失配置或依赖时，在应用装配阶段抛出。"""
