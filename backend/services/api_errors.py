from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }


def raise_api_error(
    code: str,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Any = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=error_payload(code, message, details),
    )


async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = error_payload(
            code=_code_for_status(exc.status_code),
            message=str(exc.detail or "Request failed."),
        )
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    details = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item.get("loc", []) if part != "body")
        details.append({
            "field": location or "request",
            "message": item.get("msg", "Invalid value."),
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(
            "VALIDATION_ERROR",
            "Please check the submitted values and try again.",
            details,
        ),
    )


def _code_for_status(status_code: int) -> str:
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "AUTH_REQUIRED"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "FORBIDDEN"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "NOT_FOUND"
    if status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        return "UPLOAD_TOO_LARGE"
    if status_code >= 500:
        return "INTERNAL_ERROR"
    return "REQUEST_ERROR"
