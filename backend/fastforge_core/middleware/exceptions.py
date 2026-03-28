"""
FastForge Exception Handling
================================
standardized error responses.

Catches exceptions and returns consistent JSON:
{
  "error": {
    "code": "NotFound",
    "message": "Product with id 42 not found",
    "details": null
  }
}
"""
from __future__ import annotations
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
import logging

logger = logging.getLogger("fastforge")


class BusinessException(Exception):
    """
    Base exception for business rule violations.
    

    Usage:
        raise BusinessException("Cannot delete product with active orders")
        raise BusinessException("Insufficient stock", code="InsufficientStock")
    """
    def __init__(self, message: str, code: str = "BusinessError", details: str = None):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(message)


class EntityNotFoundException(BusinessException):
    """Raised when an entity is not found."""
    def __init__(self, entity_name: str, entity_id):
        super().__init__(
            message=f"{entity_name} with id {entity_id} not found",
            code="NotFound",
        )


class UnauthorizedException(BusinessException):
    """Raised when user is not authenticated."""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, code="Unauthorized")


class ForbiddenException(BusinessException):
    """Raised when user lacks permission."""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message=message, code="Forbidden")


def register_exception_handlers(app: FastAPI, debug: bool = False):
    """
    Register all exception handlers on the FastAPI app.
    Call this in your main.py after creating the app.
    """

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        status_code = status.HTTP_400_BAD_REQUEST
        if exc.code == "NotFound":
            status_code = status.HTTP_404_NOT_FOUND
        elif exc.code == "Unauthorized":
            status_code = status.HTTP_401_UNAUTHORIZED
        elif exc.code == "Forbidden":
            status_code = status.HTTP_403_FORBIDDEN

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": _status_to_code(exc.status_code),
                    "message": str(exc.detail),
                    "details": None,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            field = " → ".join(str(loc) for loc in err["loc"])
            errors.append({"field": field, "message": err["msg"]})

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "ValidationError",
                    "message": "One or more validation errors occurred",
                    "details": errors,
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        content = {
            "error": {
                "code": "InternalError",
                "message": "An unexpected error occurred",
                "details": str(exc) if debug else None,
            }
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content,
        )


def _status_to_code(status_code: int) -> str:
    codes = {
        400: "BadRequest",
        401: "Unauthorized",
        403: "Forbidden",
        404: "NotFound",
        409: "Conflict",
        422: "ValidationError",
        429: "TooManyRequests",
        500: "InternalError",
    }
    return codes.get(status_code, f"Error{status_code}")
