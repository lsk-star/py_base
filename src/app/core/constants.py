from enum import StrEnum


class HeaderName(StrEnum):
    REQUEST_ID = "X-Request-ID"
    TRACE_ID = "X-Trace-ID"
    TRACEPARENT = "traceparent"


DEFAULT_SUCCESS_MESSAGE = "ok"

