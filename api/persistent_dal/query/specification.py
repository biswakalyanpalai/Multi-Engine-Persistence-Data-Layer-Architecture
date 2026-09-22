"""
Query Specification and Filter Criteria Layer
"""

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class FilterOperator(str, Enum):
    """Operators supported for filtering entities in the data layer."""
    EQ = "eq"              # Equals
    NEQ = "neq"            # Not Equals
    GT = "gt"              # Greater Than
    GTE = "gte"            # Greater Than or Equal
    LT = "lt"              # Less Than
    LTE = "lte"            # Less Than or Equal
    IN = "in"              # Field in list
    NOT_IN = "not_in"      # Field not in list
    CONTAINS = "contains"  # String substring match
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class SortOrder(str, Enum):
    """Sorting directions."""
    ASC = "asc"
    DESC = "desc"


class FilterCriteria(BaseModel):
    """Individual filter rule applied against an entity field."""
    field: str = Field(..., description="Target field name on the entity")
    operator: FilterOperator = Field(default=FilterOperator.EQ, description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")


class Specification(BaseModel):
    """
    Query Specification encapsulating search criteria, sorting, and pagination options.
    """
    filters: List[FilterCriteria] = Field(default_factory=list, description="Filter rules list")
    sort_by: Optional[str] = Field(default=None, description="Field name to sort results by")
    sort_order: SortOrder = Field(default=SortOrder.ASC, description="Sorting direction (asc/desc)")
    limit: Optional[int] = Field(default=None, ge=1, description="Maximum number of records to return")
    offset: Optional[int] = Field(default=None, ge=0, description="Number of records to skip")
    include_deleted: bool = Field(default=False, description="Include soft-deleted entities")

    def add_filter(self, field: str, operator: FilterOperator, value: Any) -> "Specification":
        """Chainable helper to add a filter criteria."""
        self.filters.append(FilterCriteria(field=field, operator=operator, value=value))
        return self

    def set_sorting(self, field: str, order: SortOrder = SortOrder.ASC) -> "Specification":
        """Chainable helper to set sorting configuration."""
        self.sort_by = field
        self.sort_order = order
        return self

    def set_pagination(self, limit: int, offset: int = 0) -> "Specification":
        """Chainable helper to configure pagination."""
        self.limit = limit
        self.offset = offset
        return self
