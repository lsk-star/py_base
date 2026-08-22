from fastapi import FastAPI

from pybase.presentation.middleware.access_log import AccessLogMiddleware
from pybase.presentation.middleware.request_context import RequestContextMiddleware


def register_middlewares(app: FastAPI) -> None:
    """按从外到内的执行顺序注册中间件。"""
    # FastAPI 后注册的中间件位于更外层，因此请求上下文必须最后注册。
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestContextMiddleware)
