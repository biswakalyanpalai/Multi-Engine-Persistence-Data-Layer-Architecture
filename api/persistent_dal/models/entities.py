"""
Concrete Domain Entities for Demonstration and Applications
"""

from typing import Optional, List, Dict, Any
from pydantic import Field, EmailStr
from .base import BaseEntity


class User(BaseEntity):
    """User domain entity."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., description="User full display name")
    role: str = Field(default="user", description="System access role (admin, user, guest)")
    is_active: bool = Field(default=True, description="Account active status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata attributes")


class Document(BaseEntity):
    """Document domain entity representing structured persistent files/articles."""
    title: str = Field(..., min_length=1, max_length=255, description="Document title")
    content: str = Field(default="", description="Document body content")
    author_id: str = Field(..., description="User ID of document author")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    status: str = Field(default="draft", description="Status: draft, published, archived")


class AuditLog(BaseEntity):
    """AuditLog domain entity recording system transactions."""
    action: str = Field(..., description="Performed action (CREATE, UPDATE, DELETE)")
    entity_name: str = Field(..., description="Target entity class name")
    entity_id: str = Field(..., description="Target entity UUID string")
    performed_by: str = Field(..., description="User/System identifier")
    details: Dict[str, Any] = Field(default_factory=dict, description="Audit detail payload")
