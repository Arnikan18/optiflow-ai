from pydantic import BaseModel
from typing import Generic, TypeVar, Any
from datetime import datetime

T = TypeVar('T')

class ToolResponseEnvelope(BaseModel, Generic[T]):
    requestId: str
    scenarioId: str
    sourceService: str
    sourceUpdatedAt: str  # ISO timestamp
    retrievedAt: str     # ISO timestamp
    data: T
