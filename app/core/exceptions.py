"""
AEGIS UNIFIED DATA CORE - Core Exceptions
"""
from typing import Optional, Any, Dict


class AegisCoreException(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ProviderException(AegisCoreException):
    def __init__(self, message: str, provider_name: str, status_code: int = 502, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="PROVIDER_ERROR", status_code=status_code, details={"provider": provider_name, **(details or {})})


class ValidationException(AegisCoreException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VALIDATION_ERROR", status_code=422, details=details)


class AuthenticationException(AegisCoreException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, code="UNAUTHORIZED", status_code=401)


class PermissionDeniedException(AegisCoreException):
    def __init__(self, message: str = "Insufficient privileges"):
        super().__init__(message, code="FORBIDDEN", status_code=403)


class ResourceNotFoundException(AegisCoreException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="NOT_FOUND", status_code=404)
