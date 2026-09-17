from typing import Any, Generic, TypeVar

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.constants import DEFAULT_SUCCESS_MESSAGE
from app.core.context import request_id_var, trace_id_var
from app.core.errors import ErrorCode

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    code: str
    message: str
    data: T | None = None
    request_id: str | None = None
    trace_id: str | None = None


def _to_json_content(payload: ApiResponse[Any]) -> dict[str, Any]:
    """保持 data 字段稳定，仅在未启用追踪时省略 trace_id。"""
    excluded_fields = {"trace_id"} if payload.trace_id is None else set()
    return jsonable_encoder(payload.model_dump(exclude=excluded_fields))


def success_response(data: Any = None, message: str = DEFAULT_SUCCESS_MESSAGE, status_code: int = 200) -> JSONResponse:
    payload = ApiResponse[Any](
        success=True,
        code="SUCCESS",
        message=message,
        data=data,
        request_id=request_id_var.get(),
        trace_id=trace_id_var.get(),
    )
    return JSONResponse(
        status_code=status_code,
        content=_to_json_content(payload),
    )


def error_response(
    code: ErrorCode | str,
    message: str,
    *,
    status_code: int,
    details: Any = None,
) -> JSONResponse:
    payload = ApiResponse[Any](
        success=False,
        code=str(code),
        message=message,
        data=details,
        request_id=request_id_var.get(),
        trace_id=trace_id_var.get(),
    )
    return JSONResponse(
        status_code=status_code,
        content=_to_json_content(payload),
    )
