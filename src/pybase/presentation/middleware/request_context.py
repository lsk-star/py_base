import re
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from pybase.core.constants import HeaderName
from pybase.core.context import bind_request_context, reset_request_context


_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._~-]{1,128}\Z")
_TRACE_ID_PATTERN = re.compile(r"[0-9a-fA-F]{32}\Z")
_TRACEPARENT_PATTERN = re.compile(
    r"(?P<version>[0-9a-fA-F]{2})-"
    r"(?P<trace_id>[0-9a-fA-F]{32})-"
    r"(?P<parent_id>[0-9a-fA-F]{16})-"
    r"(?P<flags>[0-9a-fA-F]{2})\Z"
)


def _safe_request_id(value: str | None) -> str:
    """接受可安全写入日志和响应头的请求标识，否则生成新标识。"""
    if value and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return uuid.uuid4().hex


def _safe_trace_id(value: str | None) -> str | None:
    """只接受 W3C 兼容的 32 位十六进制 trace_id。"""
    if value and _TRACE_ID_PATTERN.fullmatch(value) and set(value.lower()) != {"0"}:
        return value.lower()
    return None


def _trace_id_from_traceparent(value: str | None) -> str | None:
    """从 W3C traceparent 请求头中提取 trace_id。"""
    if not value:
        return None
    match = _TRACEPARENT_PATTERN.fullmatch(value)
    if match is None or match["version"].lower() == "ff":
        return None
    if set(match["trace_id"].lower()) == {"0"} or set(match["parent_id"].lower()) == {"0"}:
        return None
    return match["trace_id"].lower()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """建立当前请求的上下文，并将标识回写到响应头。"""

    async def dispatch(self, request: Request, call_next):
        request_id = _safe_request_id(request.headers.get(HeaderName.REQUEST_ID))
        trace_id = None
        if request.app.state.settings.tracing.enabled:
            trace_id = _safe_trace_id(request.headers.get(HeaderName.TRACE_ID))
            if trace_id is None:
                trace_id = _trace_id_from_traceparent(request.headers.get(HeaderName.TRACEPARENT))

        tokens = bind_request_context(request_id, trace_id)
        try:
            response = await call_next(request)
            response.headers[HeaderName.REQUEST_ID] = request_id
            if trace_id:
                response.headers[HeaderName.TRACE_ID] = trace_id
            return response
        finally:
            reset_request_context(tokens)
