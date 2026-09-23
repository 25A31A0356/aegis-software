"""
AEGIS UNIFIED DATA CORE - Common Schemas & API Envelopes
Ensures all responses carry standard provenance, freshness, and structured status.
"""
from typing import TypeVar, Generic, Optional, Any, Dict, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field

T = TypeVar("T")


class ProvenanceMetadata(BaseModel):
    data_type: str = Field(default="official_observation", description="official_observation | derived | forecast | ai_analysis | cached")
    source_authority: str = Field(default="AEGIS Data Core", description="Official agency or processing engine name")
    processing_version: str = Field(default="1.0.0", description="AEGIS processing pipeline version")
    transformation_applied: Optional[str] = Field(default=None, description="Recorded unit/field normalization rule")


class FreshnessMetadata(BaseModel):
    status: str = Field(default="fresh", description="fresh | stale | expired")
    age_seconds: int = Field(default=0, description="Age of data in seconds since observation")
    observed_at: Optional[str] = Field(default=None)
    received_at: Optional[str] = Field(default=None)
    valid_until: Optional[str] = Field(default=None)


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    freshness: Optional[FreshnessMetadata] = None
    provenance: Optional[ProvenanceMetadata] = None
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[Dict[str, Any]] = None


class PaginatedList(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int
    has_more: bool
