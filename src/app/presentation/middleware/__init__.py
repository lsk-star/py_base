"""HTTP 中间件及其统一注册入口。"""

from app.presentation.middleware.registration import register_middlewares

__all__ = ["register_middlewares"]

