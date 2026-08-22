from fastapi import APIRouter, Request

from pybase.presentation.responses import success_response

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", summary="Application information")
async def application_info(request: Request):
    settings = request.app.state.settings
    return success_response(
        {
            "name": settings.app.name,
            "environment": settings.app.environment,
            "version": "0.1.0",
        }
    )

