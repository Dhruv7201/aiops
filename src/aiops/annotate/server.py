"""FastAPI application for the annotation tool.

The only module importing fastapi — install with: pip install 'aiops[annotate]'
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from aiops.annotate.assign import round_robin_assign
from aiops.annotate.export import run_export
from aiops.annotate.models import (
    AssignRequest,
    CreateProjectRequest,
    CreateUserRequest,
    ExportRequest,
    ExportResult,
    ImageInfo,
    LabelMeDoc,
    ProjectMeta,
    ProjectSummary,
    ReassignRequest,
    SetLabelsRequest,
)
from aiops.annotate.storage import ProjectStore
from aiops.core.config import get_settings
from aiops.core.log import get_logger

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

MISSING_FRONTEND_HTML = """<!doctype html>
<html><body style="font-family: sans-serif; max-width: 40em; margin: 4em auto">
<h1>aiops annotate</h1>
<p>The API is running, but the frontend has not been built.</p>
<p>Either run <code>make frontend</code> and restart, or use the Vite dev
server: <code>cd frontend && npm run dev</code> and open
<a href="http://localhost:5173">http://localhost:5173</a>.</p>
</body></html>"""


def create_app(annotate_dir: Path | None = None) -> FastAPI:
    """Build the annotation FastAPI app around a ProjectStore."""
    store = ProjectStore(annotate_dir or get_settings().annotate_dir)
    app = FastAPI(title="aiops annotate", version="0.1.0")
    app.state.store = store

    # Per-project locks around project.json read-modify-write
    locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _project_or_404(name: str) -> ProjectMeta:
        try:
            return store.load_project(name)
        except KeyError:
            raise HTTPException(404, f"Unknown project '{name}'")

    # -- Health --

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    # -- Users --

    @app.get("/api/users")
    async def list_users() -> list[str]:
        return store.list_users()

    @app.post("/api/users", status_code=201)
    async def create_user(req: CreateUserRequest) -> list[str]:
        return store.add_user(req.name)

    # -- Projects --

    @app.get("/api/projects")
    async def list_projects() -> list[ProjectSummary]:
        return store.list_projects()

    @app.post("/api/projects", status_code=201)
    async def create_project(req: CreateProjectRequest) -> ProjectMeta:
        try:
            return store.create_project(req.name, req.images_dir)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
        except FileExistsError as e:
            raise HTTPException(409, str(e))

    @app.get("/api/projects/{name}")
    async def get_project(name: str) -> ProjectMeta:
        return _project_or_404(name)

    @app.put("/api/projects/{name}/labels")
    async def set_labels(name: str, req: SetLabelsRequest) -> ProjectMeta:
        _project_or_404(name)
        async with locks[name]:
            return store.set_labels(name, req.labels)

    # -- Images --

    @app.get("/api/projects/{name}/images")
    async def list_images(name: str) -> list[ImageInfo]:
        _project_or_404(name)
        return store.list_images(name)

    @app.get("/api/projects/{name}/images/{filename}")
    async def get_image(name: str, filename: str) -> FileResponse:
        _project_or_404(name)
        try:
            return FileResponse(store.image_path(name, filename))
        except FileNotFoundError:
            raise HTTPException(404, f"Image not found: {filename}")

    # -- Assignment --

    @app.post("/api/projects/{name}/assign")
    async def assign_images(name: str, req: AssignRequest) -> ProjectMeta:
        meta = _project_or_404(name)
        if not req.users:
            raise HTTPException(422, "at least one user is required")
        async with locks[name]:
            assignments = round_robin_assign(
                store.list_image_files(name),
                req.users,
                existing=meta.assignments,
                keep_existing=req.keep_existing,
            )
            meta = store.set_assignments(name, assignments)
            # Track users participating in the project
            meta.users = sorted(set(meta.users) | set(req.users))
            store.save_project(meta)
        return meta

    @app.put("/api/projects/{name}/assign")
    async def reassign_image(name: str, req: ReassignRequest) -> ProjectMeta:
        _project_or_404(name)
        if req.filename not in store.list_image_files(name):
            raise HTTPException(404, f"Image not found: {req.filename}")
        async with locks[name]:
            meta = store.load_project(name)
            if req.user:
                meta.assignments[req.filename] = req.user
                if req.user not in meta.users:
                    meta.users.append(req.user)
            else:
                meta.assignments.pop(req.filename, None)
            store.save_project(meta)
        return meta

    # -- Annotations --

    @app.get("/api/projects/{name}/annotations/{filename}")
    async def get_annotation(name: str, filename: str) -> LabelMeDoc:
        _project_or_404(name)
        try:
            store.image_path(name, filename)  # validates filename
            return store.load_annotation(name, filename)
        except FileNotFoundError:
            raise HTTPException(404, f"Image not found: {filename}")

    @app.put("/api/projects/{name}/annotations/{filename}")
    async def save_annotation(name: str, filename: str, doc: LabelMeDoc) -> dict:
        _project_or_404(name)
        try:
            store.image_path(name, filename)  # validates filename
        except FileNotFoundError:
            raise HTTPException(404, f"Image not found: {filename}")
        # Last-write-wins for v1; saves are atomic whole-file replaces
        store.save_annotation(name, filename, doc)
        return {"saved": True}

    # -- Export --

    @app.post("/api/projects/{name}/export")
    async def export_project(name: str, req: ExportRequest) -> ExportResult:
        _project_or_404(name)
        try:
            return run_export(store, name, req)
        except KeyError as e:
            raise HTTPException(422, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    # -- Frontend (built SPA) --

    if (STATIC_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    else:
        logger.warning(
            "Frontend not built (missing %s) — API only. Run 'make frontend'.",
            STATIC_DIR / "index.html",
        )

        @app.get("/", response_class=HTMLResponse)
        async def missing_frontend() -> str:
            return MISSING_FRONTEND_HTML

    return app
