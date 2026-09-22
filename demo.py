"""
Persistent Data Layer Architecture - Demonstration Script
=========================================================
Runs through real usage scenarios for all storage engines, query specifications,
transactional Unit of Work, write-through caching, and high-level DataService.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from persistent_dal import (
    BaseEntity,
    User,
    Document,
    AuditLog,
    MemoryRepository,
    JSONFileRepository,
    SQLiteRepository,
    CachedRepository,
    Specification,
    FilterOperator,
    SortOrder,
    UnitOfWork,
    DataService,
)


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"   {title}")
    print("=" * 70)


async def main():
    print_header("PERSISTENT DATA LAYER FRAMEWORK DEMO")

    # Temp workspace directory for demonstration databases and file stores
    demo_dir = Path(tempfile.mkdtemp(prefix="dal_demo_"))
    json_path = demo_dir / "storage" / "documents.json"
    sqlite_path = demo_dir / "storage" / "enterprise.db"

    try:
        # ---------------------------------------------------------------------
        # 1. In-Memory Engine & Specification Filtering
        # ---------------------------------------------------------------------
        print_header("1. In-Memory Engine & Query Specifications")
        user_mem_repo = MemoryRepository(User)

        users_to_create = [
            User(username="dev_alex", email="alex@company.com", full_name="Alex Rivera", role="admin"),
            User(username="dev_beatrice", email="beatrice@company.com", full_name="Beatrice Vance", role="developer"),
            User(username="mgr_carlos", email="carlos@company.com", full_name="Carlos Mendoza", role="manager"),
            User(username="dev_dylan", email="dylan@company.com", full_name="Dylan Brooks", role="developer"),
        ]

        await user_mem_repo.add_many(users_to_create)
        print(f"[OK] Added {await user_mem_repo.count()} users into In-Memory repository.")

        # Query using Specification
        spec = Specification()
        spec.add_filter("role", FilterOperator.EQ, "developer")
        spec.set_sorting("username", SortOrder.ASC)

        devs = await user_mem_repo.find(spec)
        print(f"[OK] Found {len(devs)} developers (sorted ASC):")
        for dev in devs:
            print(f"   * [{dev.id}] {dev.username} ({dev.full_name}) - {dev.email}")

        # ---------------------------------------------------------------------
        # 2. JSON File Storage Engine (Atomic Writes)
        # ---------------------------------------------------------------------
        print_header("2. JSON File Storage Engine (Atomic File Persistence)")
        doc_json_repo = JSONFileRepository(Document, json_path)

        doc1 = Document(
            title="System Architecture Spec v1",
            content="Persistent Data Layer design pattern implementation details...",
            author_id=str(users_to_create[0].id),
            tags=["architecture", "python", "design"],
            status="published"
        )
        doc2 = Document(
            title="Database Migration Guidelines",
            content="Steps for executing safe migrations...",
            author_id=str(users_to_create[1].id),
            tags=["database", "devops"],
            status="draft"
        )

        await doc_json_repo.add_many([doc1, doc2])
        print(f"[OK] Written {await doc_json_repo.count()} documents to JSON file storage: '{json_path}'")
        print(f"[OK] File exists on disk, size: {json_path.stat().st_size} bytes.")

        # Verify Reloading from Disk
        fresh_json_repo = JSONFileRepository(Document, json_path)
        reloaded_docs = await fresh_json_repo.list_all()
        print(f"[OK] Reloaded {len(reloaded_docs)} documents from file on disk cleanly.")

        # ---------------------------------------------------------------------
        # 3. Asynchronous SQLite Relational Engine
        # ---------------------------------------------------------------------
        print_header("3. Asynchronous SQLite Relational Storage Engine")
        sqlite_repo = SQLiteRepository(User, sqlite_path)

        for u in users_to_create:
            await sqlite_repo.add(u)

        print(f"[OK] Initialized SQLite table 'users' in database: '{sqlite_path}'")
        print(f"[OK] Persisted {await sqlite_repo.count()} users in SQLite.")

        # Filter query on SQLite engine
        search_spec = Specification().add_filter("email", FilterOperator.CONTAINS, "company.com")
        sqlite_results = await sqlite_repo.find(search_spec)
        print(f"[OK] SQLite Search matched {len(sqlite_results)} records matching 'company.com'.")

        # ---------------------------------------------------------------------
        # 4. Cached Repository Decorator Tier
        # ---------------------------------------------------------------------
        print_header("4. Tiered Read-Through / Write-Through Caching Layer")
        cached_repo = CachedRepository(sqlite_repo, ttl_seconds=120)

        # First lookup -> Read-Through from SQLite underlying storage
        test_id = users_to_create[0].id
        print("Executing 1st get_by_id call...")
        _ = await cached_repo.get_by_id(test_id)
        print(f"   Cache Stats -> Hits: {cached_repo.hits}, Misses: {cached_repo.misses}, Hit Ratio: {cached_repo.hit_ratio:.1%}")

        print("Executing 2nd & 3rd get_by_id calls for same entity...")
        _ = await cached_repo.get_by_id(test_id)
        _ = await cached_repo.get_by_id(test_id)
        print(f"   Cache Stats -> Hits: {cached_repo.hits}, Misses: {cached_repo.misses}, Hit Ratio: {cached_repo.hit_ratio:.1%}")

        # ---------------------------------------------------------------------
        # 5. Transactional Unit of Work (UoW) Pattern
        # ---------------------------------------------------------------------
        print_header("5. Unit of Work (UoW) Transaction Management")
        uow_users = MemoryRepository(User)
        uow_docs = MemoryRepository(Document)
        factories = {User: uow_users, Document: uow_docs}

        print("Executing successful transaction block...")
        async with UnitOfWork(factories) as uow:
            u_repo = uow.get_repository(User)
            d_repo = uow.get_repository(Document)

            new_user = User(username="tx_user", email="tx@example.com", full_name="Tx User")
            await u_repo.add(new_user)

            new_doc = Document(title="Transactional Document", author_id=str(new_user.id), content="Tx body")
            await d_repo.add(new_doc)

        print(f"[OK] Context block exited cleanly. Committed: {uow.committed}")
        print(f"[OK] Repositories updated -> Users: {await uow_users.count()}, Docs: {await uow_docs.count()}")

        print("\nExecuting failed transaction block (Simulating Rollback)...")
        try:
            async with UnitOfWork(factories) as uow:
                u_repo = uow.get_repository(User)
                await u_repo.add(User(username="bad_user", email="bad@example.com", full_name="Bad User"))
                raise RuntimeError("Uncaught Database Error!")
        except RuntimeError as e:
            print(f"[OK] Exception caught: '{e}'. Transaction rolled back cleanly: {uow.rolled_back}")

        # ---------------------------------------------------------------------
        # 6. High-Level DataService Facade
        # ---------------------------------------------------------------------
        print_header("6. High-Level DataService Facade & Audit Logging")
        audit_repo = MemoryRepository(AuditLog)
        service = DataService(uow_users, uow_docs, audit_repo)

        svc_user = await service.register_user("tech_lead", "lead@domain.com", "Tech Lead")
        doc = await service.create_document(str(svc_user.id), "Production Deployment Manual", "Content...")
        published_doc = await service.publish_document(doc.id, str(svc_user.id))

        stats = await service.get_summary_stats()
        print(f"[OK] Summary Statistics: {stats}")

        audit_logs = await audit_repo.list_all()
        print(f"[OK] Audit Logs Recorded ({len(audit_logs)} entries):")
        for log in audit_logs:
            print(f"   * [{log.created_at.strftime('%H:%M:%S')}] ACTION={log.action:<8} ENTITY={log.entity_name:<10} BY={log.performed_by}")

        print_header("ALL PERSISTENT DATA LAYER DEMONSTRATIONS COMPLETED SUCCESSFULLY!")

    finally:
        # Clean up temporary test directories
        shutil.rmtree(demo_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
