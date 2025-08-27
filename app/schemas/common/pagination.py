from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")

class PaginatedResponse(GenericModel, Generic[T]):
    data: List[T]
    total: int
    skip: int
    limit: int


class PaginatedResponseNew(GenericModel, Generic[T]):
    page_index: int
    page_size: int
    count: int
    data: List[T]
