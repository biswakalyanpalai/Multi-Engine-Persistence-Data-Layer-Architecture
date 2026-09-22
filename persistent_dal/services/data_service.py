"""
High-Level Data Service Facade
"""

from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from ..models.entities import User, Document, AuditLog
from ..repositories.base import AbstractRepository
from ..query.specification import Specification, FilterCriteria, FilterOperator, SortOrder
from ..unit_of_work import UnitOfWork


class DataService:
    """
    Business logic facade encapsulating cross-repository operations,
    audit tracking, backup/export capabilities, and domain workflows.
    """

    def __init__(
        self,
        user_repo: AbstractRepository[User],
        doc_repo: AbstractRepository[Document],
        audit_repo: Optional[AbstractRepository[AuditLog]] = None
    ):
        self.users = user_repo
        self.documents = doc_repo
        self.audit_logs = audit_repo

    async def _log_audit(self, action: str, entity_name: str, entity_id: str, actor: str, details: Dict[str, Any]) -> None:
        """Helper to create audit records if an audit repository is configured."""
        if self.audit_logs:
            log = AuditLog(
                action=action,
                entity_name=entity_name,
                entity_id=entity_id,
                performed_by=actor,
                details=details
            )
            await self.audit_logs.add(log)

    async def register_user(self, username: str, email: str, full_name: str, role: str = "user") -> User:
        """Register a new user entity with uniqueness check and audit log."""
        # Check if username exists
        spec = Specification().add_filter("username", FilterOperator.EQ, username)
        existing = await self.users.find(spec)
        if existing:
            raise ValueError(f"Username '{username}' is already registered.")

        user = User(username=username, email=email, full_name=full_name, role=role)
        created_user = await self.users.add(user)
        await self._log_audit("CREATE", "User", str(created_user.id), "system", {"username": username, "email": email})
        return created_user

    async def create_document(self, author_id: str, title: str, content: str, tags: Optional[List[str]] = None) -> Document:
        """Create a new document linked to an author."""
        doc = Document(
            author_id=author_id,
            title=title,
            content=content,
            tags=tags or [],
            status="draft"
        )
        created_doc = await self.documents.add(doc)
        await self._log_audit("CREATE", "Document", str(created_doc.id), author_id, {"title": title})
        return created_doc

    async def publish_document(self, doc_id: Union[UUID, str], actor_id: str) -> Document:
        """Publish a document by updating status."""
        doc = await self.documents.get_by_id(doc_id)
        if not doc:
            raise KeyError(f"Document '{doc_id}' not found.")

        doc.status = "published"
        updated_doc = await self.documents.update(doc)
        await self._log_audit("UPDATE", "Document", str(doc_id), actor_id, {"status": "published"})
        return updated_doc

    async def search_documents(
        self,
        query: Optional[str] = None,
        author_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Document]:
        """Search documents using flexible specification filtering."""
        spec = Specification()
        if author_id:
            spec.add_filter("author_id", FilterOperator.EQ, author_id)
        if status:
            spec.add_filter("status", FilterOperator.EQ, status)
        if query:
            spec.add_filter("title", FilterOperator.CONTAINS, query)

        spec.set_sorting("created_at", SortOrder.DESC)
        spec.set_pagination(limit=limit, offset=offset)

        return await self.documents.find(spec)

    async def get_summary_stats(self) -> Dict[str, Any]:
        """Retrieve aggregated storage metrics across entities."""
        total_users = await self.users.count()
        total_docs = await self.documents.count()
        published_docs = await self.documents.count(Specification().add_filter("status", FilterOperator.EQ, "published"))
        total_audits = await self.audit_logs.count() if self.audit_logs else 0

        return {
            "total_users": total_users,
            "total_documents": total_docs,
            "published_documents": published_docs,
            "total_audit_logs": total_audits
        }
