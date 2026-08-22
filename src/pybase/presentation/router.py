from fastapi import APIRouter

from pybase.core.config import Settings
from pybase.modules.registry import register_modules
from pybase.modules.system.router import router as system_router


def build_api_router(settings: Settings) -> APIRouter:
    """业务模块增长时，在这里注册所有版本化 API 路由。"""
    router = APIRouter()
    router.include_router(system_router)
    register_modules(router, database_enabled=settings.database.enabled)
    return router
