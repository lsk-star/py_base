from fastapi import APIRouter

from pybase.modules.system.router import router as system_router


def build_api_router() -> APIRouter:
    """业务模块增长时，在这里注册所有版本化 API 路由。"""
    router = APIRouter()
    router.include_router(system_router)
    return router
