from fastapi import HTTPException, status

class BaseAppException(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)

class ValidationError(BaseAppException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

class NotFoundError(BaseAppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class InsufficientStockError(HTTPException):
    def __init__(self, detail: str = "Insufficient stock available"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
