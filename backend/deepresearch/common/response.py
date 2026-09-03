"""Unified API response envelope used by all FastAPI endpoints."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None
    code: str | None = None


def ok(data: Any = None) -> ApiResponse:
    return ApiResponse(success=True, data=data)


def err(message: str, *, code: str = "ERROR") -> ApiResponse:
    return ApiResponse(success=False, error=message, code=code)
