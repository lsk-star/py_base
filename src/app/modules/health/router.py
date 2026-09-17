from fastapi import APIRouter, Request

from app.contracts.lifecycle import ComponentRegistry
from app.core.errors import ErrorCode
from app.presentation.responses import error_response, success_response

router = APIRouter(tags=["health"])


@router.get("/live", summary="Liveness probe")
async def liveness():
    """只证明 HTTP 应用仍在运行，不探测任何外部依赖。"""
    return success_response({"status": "alive"})


@router.get("/ready", summary="Readiness probe")
async def readiness(request: Request):
    registry: ComponentRegistry = request.app.state.components
    checks = await registry.readiness()
    ready = all(check.ready for check in checks)
    data = {
        "status": "ready" if ready else "not_ready",
        "checks": [check.__dict__ for check in checks],
    }
    if not ready:
        return error_response(
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "服务暂未就绪",
            status_code=503,
            details=data,
        )
    return success_response(data)
