import logging
from time import perf_counter

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

access_logger = logging.getLogger("pybase.access")

_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "client_secret",
        "code",
        "cookie",
        "id_token",
        "password",
        "refresh_token",
        "secret",
        "token",
    }
)

_SENSITIVE_QUERY_KEY_PARTS = ("password", "secret", "token", "authorization", "cookie")


def _is_sensitive_query_key(key: str) -> bool:
    normalized_key = key.lower().replace("-", "_")
    return (
        normalized_key in _SENSITIVE_QUERY_KEYS
        or any(part in normalized_key for part in _SENSITIVE_QUERY_KEY_PARTS)
    )


def _safe_query_params(request: Request) -> dict[str, str | list[str]]:
    """返回可记录的查询参数，不记录请求体、Cookie 或认证头。"""
    max_length = request.app.state.settings.logging.max_query_value_length
    result: dict[str, str | list[str]] = {}
    for key, value in request.query_params.multi_items():
        safe_value = "***" if _is_sensitive_query_key(key) else value[:max_length]
        existing = result.get(key)
        if existing is None:
            result[key] = safe_value
        elif isinstance(existing, list):
            existing.append(safe_value)
        else:
            result[key] = [existing, safe_value]
    return result


class AccessLogMiddleware(BaseHTTPMiddleware):
    """记录请求与响应日志，日志上下文由外层请求上下文中间件提供。"""

    async def dispatch(self, request: Request, call_next):
        if not request.app.state.settings.logging.access_log:
            return await call_next(request)

        started_at = perf_counter()
        access_logger.info(
            "请求 method=%s path=%s query=%s",
            request.method,
            request.url.path,
            _safe_query_params(request),
        )
        try:
            response = await call_next(request)
        except Exception:
            access_logger.exception(
                "响应异常 method=%s path=%s duration_ms=%.2f ms",
                request.method,
                request.url.path,
                (perf_counter() - started_at) * 1000,
            )
            raise

        access_logger.info(
            "响应 method=%s path=%s status_code=%s duration_ms=%.2f ms",
            request.method,
            request.url.path,
            response.status_code,
            (perf_counter() - started_at) * 1000,
        )
        return response
