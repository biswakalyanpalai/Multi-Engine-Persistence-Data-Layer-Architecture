"""
Base Entity Definition for Persistent Data Layer
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone information."""
    return datetime.now(timezone.utc)


class BaseEntity(BaseModel):
    """
    Base class for all domain entities in the Persistent Data Layer.
    Provides standard fields: id, created_at, updated_at, is_deleted, version.
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )

    id: UUID = Field(default_factory=uuid4, description="Unique Entity Identifier (UUIDv4)")
    created_at: datetime = Field(default_factory=utc_now, description="Entity Creation Timestamp")
    updated_at: datetime = Field(default_factory=utc_now, description="Entity Last Updated Timestamp")
    is_deleted: bool = Field(default=False, description="Soft-delete status flag")
    version: int = Field(default=1, description="Optimistic locking version counter")

    def touch(self) -> None:
        """Update entity updated_at timestamp and bump version counter."""
        self.updated_at = utc_now()
        self.version += 1

    def mark_deleted(self) -> None:
        """Mark entity as soft deleted."""
        self.is_deleted = True
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity model to a plain dictionary representation."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseEntity":
        """Reconstruct entity model from dictionary."""
        return cls.model_validate(data)
