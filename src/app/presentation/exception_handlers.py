import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ErrorCode
from app.core.exceptions import AppError
from app.presentation.responses import error_response

logger = logging.getLogger(__name__)

_HTTP_ERROR_CODES = {
    HTTPStatus.BAD_REQUEST: ErrorCode.BAD_REQUEST,
    HTTPStatus.UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
    HTTPStatus.FORBIDDEN: ErrorCode.FORBIDDEN,
    HTTPStatus.NOT_FOUND: ErrorCode.NOT_FOUND,
    HTTPStatus.CONFLICT: ErrorCode.CONFLICT,
    HTTPStatus.TOO_MANY_REQUESTS: ErrorCode.TOO_MANY_REQUESTS,
    HTTPStatus.SERVICE_UNAVAILABLE: ErrorCode.DEPENDENCY_UNAVAILABLE,
}


def error_code_for_http_status(status_code: int) -> ErrorCode:
    """将 HTTP 状态码映射为稳定的业务错误码。"""
    return _HTTP_ERROR_CODES.get(status_code, ErrorCode.BAD_REQUEST)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        return error_response(exc.code, exc.message, status_code=exc.status_code, details=exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        return error_response(
            ErrorCode.VALIDATION_ERROR,
            "请求参数校验失败",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            details=exc.errors(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException):
        code = error_code_for_http_status(exc.status_code)
        return error_response(code, str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception):
        logger.exception("Unhandled application error", exc_info=exc)
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "服务内部错误",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
