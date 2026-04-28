"""Custom HTTP exceptions for clean, consistent error responses."""
from fastapi import HTTPException


class AppException(HTTPException):
    """Base for all app-specific HTTP errors."""


class NotFoundError(AppException):
    def __init__(self, resource: str, id: str):
        super().__init__(404, f"{resource} with id '{id}' not found")


class ConflictError(AppException):
    def __init__(self, msg: str):
        super().__init__(409, msg)


class WorkflowStateError(AppException):
    def __init__(self, msg: str):
        super().__init__(409, f"Workflow state error: {msg}")


class ForbiddenError(AppException):
    def __init__(self, msg: str = "Insufficient permissions"):
        super().__init__(403, msg)


class UnprocessableError(AppException):
    def __init__(self, msg: str):
        super().__init__(422, msg)


class StorageError(AppException):
    def __init__(self, msg: str):
        super().__init__(502, f"Storage error: {msg}")
