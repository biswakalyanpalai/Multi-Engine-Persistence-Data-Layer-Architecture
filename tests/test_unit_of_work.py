"""
Test Suite for Unit of Work Pattern and DataService Integration
"""

import pytest
from persistent_dal import (
    MemoryRepository,
    UnitOfWork,
    DataService,
    User,
    Document,
    AuditLog
)


@pytest.mark.asyncio
async def test_unit_of_work_commit_rollback():
    user_repo = MemoryRepository(User)
    doc_repo = MemoryRepository(Document)

    factories = {
        User: user_repo,
        Document: doc_repo
    }

    # Test clean commit on exit
    async with UnitOfWork(factories) as uow:
        u_repo = uow.get_repository(User)
        user = User(username="uow_user", email="uow@example.com", full_name="UoW User")
        await u_repo.add(user)
        assert uow.committed is False

    assert uow.committed is True
    assert await user_repo.count() == 1

    # Test automatic rollback on error exception
    with pytest.raises(RuntimeError):
        async with UnitOfWork(factories) as uow:
            u_repo = uow.get_repository(User)
            user2 = User(username="uow_error", email="error@example.com", full_name="Error User")
            await u_repo.add(user2)
            raise RuntimeError("Simulated transaction crash")

    assert uow.rolled_back is True


@pytest.mark.asyncio
async def test_data_service_workflow():
    user_repo = MemoryRepository(User)
    doc_repo = MemoryRepository(Document)
    audit_repo = MemoryRepository(AuditLog)

    service = DataService(user_repo, doc_repo, audit_repo)

    # 1. Register User
    user = await service.register_user("john_doe", "john@example.com", "John Doe")
    assert user.username == "john_doe"

    # Duplicate username prevention
    with pytest.raises(ValueError):
        await service.register_user("john_doe", "john2@example.com", "John Duplicate")

    # 2. Create and Publish Document
    doc = await service.create_document(str(user.id), "Architecture Overview", "Data Layer Content")
    assert doc.status == "draft"

    published = await service.publish_document(doc.id, str(user.id))
    assert published.status == "published"

    # 3. Search documents
    docs = await service.search_documents(query="Architecture", status="published")
    assert len(docs) == 1

    # 4. Summary stats
    stats = await service.get_summary_stats()
    assert stats["total_users"] == 1
    assert stats["total_documents"] == 1
    assert stats["published_documents"] == 1
    assert stats["total_audit_logs"] == 3
