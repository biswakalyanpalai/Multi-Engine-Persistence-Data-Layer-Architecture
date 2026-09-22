"""
Vercel Serverless Entrypoint for Multi-Engine Persistent Data Layer
"""

import sys
import os
import tempfile
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root directory and api directory are on sys.path
api_dir = Path(__file__).resolve().parent
root_dir = api_dir.parent
for d in [str(api_dir), str(root_dir)]:
    if d not in sys.path:
        sys.path.insert(0, d)

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from persistent_dal import (
        MemoryRepository,
        JSONFileRepository,
        SQLiteRepository,
        CachedRepository,
        Specification,
        FilterOperator,
        SortOrder,
        User,
        Document,
        AuditLog,
        DataService,
        UnitOfWork,
    )
except Exception:
    from api.persistent_dal import (
        MemoryRepository,
        JSONFileRepository,
        SQLiteRepository,
        CachedRepository,
        Specification,
        FilterOperator,
        SortOrder,
        User,
        Document,
        AuditLog,
        DataService,
        UnitOfWork,
    )

# Use writable /tmp directory for serverless environment
TEMP_DIR = Path(tempfile.gettempdir())
json_storage_path = TEMP_DIR / "dal_docs.json"
sqlite_storage_path = TEMP_DIR / "dal_app.db"

# Global in-memory storage repositories for serverless environment
user_repo = MemoryRepository(User)
doc_repo = MemoryRepository(Document)
audit_repo = MemoryRepository(AuditLog)
cached_user_repo = CachedRepository(user_repo, ttl_seconds=300)
service = DataService(cached_user_repo, doc_repo, audit_repo)

_initialized = False


async def ensure_seeded():
    global _initialized
    if _initialized:
        return
    try:
        if await user_repo.count() == 0:
            u1 = await service.register_user("alex_rivera", "alex@company.com", "Alex Rivera", role="admin")
            u2 = await service.register_user("beatrice_v", "beatrice@company.com", "Beatrice Vance", role="developer")
            doc = await service.create_document(str(u1.id), "Persistent Data Layer Architecture", "Multi-Engine Storage Engine for Python.")
            await service.publish_document(doc.id, str(u1.id))
    except Exception as e:
        print(f"Seed error: {e}")
    finally:
        _initialized = True


app = FastAPI(
    title="Persistent Data Layer API",
    description="A multi-engine Data Access Layer implementing Repository, Unit of Work, Query Specification, and Caching patterns.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler capturing runtime errors for diagnostic telemetry."""
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()
        }
    )


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3)
    email: str
    full_name: str
    role: str = "user"


class CreateDocumentRequest(BaseModel):
    author_id: str
    title: str
    content: str
    tags: List[str] = []


@app.get("/", response_class=HTMLResponse)
async def home_dashboard():
    """HTML Dashboard Overview for Vercel deployment."""
    await ensure_seeded()
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Multi-Engine Persistent Data Layer</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            .card { background: #1e293b; border: 1px solid #334155; color: #f8fafc; }
            .badge-custom { background-color: #3b82f6; }
            pre { background: #090d16; padding: 12px; border-radius: 6px; color: #38bdf8; }
        </style>
    </head>
    <body class="py-5">
        <div class="container">
            <div class="text-center mb-5">
                <h1 class="display-4 fw-bold text-primary">Multi-Engine Persistent Data Layer</h1>
                <p class="lead text-secondary">Enterprise Python DAL implementing Repository Pattern, Unit of Work, Query Specifications & Write-Through Caching.</p>
                <div class="mt-3">
                    <a href="/docs" class="btn btn-primary btn-lg me-2">Interactive Swagger API Docs</a>
                    <a href="/api/stats" class="btn btn-outline-light btn-lg me-2">View Data Layer Metrics</a>
                    <a href="/api/demo" class="btn btn-success btn-lg">Run Live DAL Engines Demo</a>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card h-100 p-4">
                        <h3 class="h5 text-info">Repository Pattern</h3>
                        <p class="text-secondary small">Generic Async Repository interface abstracting SQLite, File JSON, and In-Memory storage engines seamlessly.</p>
                        <span class="badge badge-custom w-auto">AbstractRepository[T]</span>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card h-100 p-4">
                        <h3 class="h5 text-warning">Unit of Work (UoW)</h3>
                        <p class="text-secondary small">Atomic transaction context manager for multi-repository state commit and automatic exception rollback.</p>
                        <span class="badge bg-warning text-dark w-auto">UnitOfWork Context Manager</span>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card h-100 p-4">
                        <h3 class="h5 text-success">Read/Write-Through Cache</h3>
                        <p class="text-secondary small">Decorated caching layer providing automatic cache invalidation and hit/miss performance analytics.</p>
                        <span class="badge bg-success w-auto">CachedRepository Tier</span>
                    </div>
                </div>
            </div>

            <div class="mt-5 card p-4">
                <h4 class="mb-3 text-white">Available API Endpoints</h4>
                <ul class="list-group list-group-flush bg-transparent">
                    <li class="list-group-item bg-transparent text-light"><code>GET /api/stats</code> - System aggregated telemetry metrics</li>
                    <li class="list-group-item bg-transparent text-light"><code>GET /api/demo</code> - Execute multi-engine live telemetry test</li>
                    <li class="list-group-item bg-transparent text-light"><code>GET /api/users</code> - List registered users with specification filtering</li>
                    <li class="list-group-item bg-transparent text-light"><code>POST /api/users</code> - Register a new user</li>
                    <li class="list-group-item bg-transparent text-light"><code>GET /api/documents</code> - Query documents specification</li>
                    <li class="list-group-item bg-transparent text-light"><code>POST /api/documents</code> - Create new document</li>
                    <li class="list-group-item bg-transparent text-light"><code>GET /api/audits</code> - Retrieve system audit logs</li>
                    <li class="list-group-item bg-transparent text-light"><code>GET /api/cache-stats</code> - Caching hit/miss analytics</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content


@app.get("/api/stats")
async def get_stats():
    """Retrieve summary metrics across repositories."""
    await ensure_seeded()
    return await service.get_summary_stats()


@app.get("/api/cache-stats")
async def get_cache_stats():
    """Retrieve caching hit/miss performance statistics."""
    await ensure_seeded()
    return {
        "hits": cached_user_repo.hits,
        "misses": cached_user_repo.misses,
        "hit_ratio_percent": round(cached_user_repo.hit_ratio * 100, 2)
    }


@app.get("/api/users")
async def list_users(role: Optional[str] = None):
    """List users filtered by role using Specification query builder."""
    await ensure_seeded()
    spec = Specification()
    if role:
        spec.add_filter("role", FilterOperator.EQ, role)
    users = await user_repo.find(spec)
    return [u.to_dict() for u in users]


@app.post("/api/users", status_code=201)
async def create_user(payload: CreateUserRequest):
    """Register a new user entity."""
    await ensure_seeded()
    try:
        user = await service.register_user(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role
        )
        return user.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/documents")
async def search_documents(
    query: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """Search documents using flexible specification query builder."""
    await ensure_seeded()
    docs = await service.search_documents(query=query, status=status, limit=limit, offset=offset)
    return [d.to_dict() for d in docs]


@app.post("/api/documents", status_code=201)
async def create_document(payload: CreateDocumentRequest):
    """Create a new document."""
    await ensure_seeded()
    doc = await service.create_document(
        author_id=payload.author_id,
        title=payload.title,
        content=payload.content,
        tags=payload.tags
    )
    return doc.to_dict()


@app.get("/api/audits")
async def get_audit_logs():
    """Retrieve system audit logs."""
    await ensure_seeded()
    logs = await audit_repo.list_all()
    return [log.to_dict() for log in logs]


@app.get("/api/demo")
async def run_live_demo():
    """Execute live multi-engine test scenario across SQLite, JSON File, and Memory stores."""
    results = []

    # 1. JSON File Engine in /tmp
    json_repo = JSONFileRepository(Document, json_storage_path)
    d1 = Document(title="Serverless Arch Spec", content="Vercel serverless DAL execution.", author_id="u_vc")
    await json_repo.add(d1)
    results.append({"engine": "JSONFileRepository", "path": str(json_storage_path), "doc_count": await json_repo.count()})

    # 2. SQLite Engine in /tmp
    sqlite_repo = SQLiteRepository(User, sqlite_storage_path)
    u_sql = User(username="sqlite_user", email="sqlite@ver.cel", full_name="SQLite User")
    await sqlite_repo.add(u_sql)
    results.append({"engine": "SQLiteRepository", "path": str(sqlite_storage_path), "user_count": await sqlite_repo.count()})

    # 3. Unit of Work Transaction
    factories = {User: MemoryRepository(User), Document: MemoryRepository(Document)}
    async with UnitOfWork(factories) as uow:
        await uow.get_repository(User).add(User(username="uow_tx", email="tx@ver.cel", full_name="UoW User"))
    results.append({"engine": "UnitOfWork", "transaction_committed": uow.committed})

    return {
        "status": "success",
        "message": "All Multi-Engine Data Access Layer operations executed cleanly on Vercel.",
        "engines_telemetry": results
    }
