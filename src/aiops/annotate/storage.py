"""JSON-file persistence for annotation projects.

Layout:
    <annotate_dir>/projects.json          — global project registry
    <annotate_dir>/users.json             — global user list
    <images_dir>/.annotations/project.json    — per-project labels/users/assignments
    <images_dir>/.annotations/<stem>.json     — LabelMe doc per image
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image

from aiops.annotate.models import (
    ImageInfo,
    LabelDef,
    LabelMeDoc,
    ProjectMeta,
    ProjectSummary,
)
from aiops.core.log import get_logger

logger = get_logger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
ANNOTATIONS_SUBDIR = ".annotations"


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically via tmp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def _read_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text())


def _check_stem_collisions(images_dir: Path) -> None:
    """Reject dirs where two images share a stem (e.g. a.jpg + a.png).

    Annotations are stored as <stem>.json, so such pairs would silently
    overwrite each other's labels.
    """
    stems: dict[str, str] = {}
    for p in images_dir.iterdir():
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            if p.stem in stems:
                raise ValueError(
                    f"Images '{stems[p.stem]}' and '{p.name}' share the same "
                    "base name; annotations would collide. Rename one of them."
                )
            stems[p.stem] = p.name


class ProjectStore:
    """File-backed store for users, projects, and annotations."""

    def __init__(self, annotate_dir: Path | str) -> None:
        self.annotate_dir = Path(annotate_dir)
        self.annotate_dir.mkdir(parents=True, exist_ok=True)

    # -- Users --

    @property
    def _users_path(self) -> Path:
        return self.annotate_dir / "users.json"

    def list_users(self) -> list[str]:
        return _read_json(self._users_path, {"users": []}).get("users", [])

    def add_user(self, name: str) -> list[str]:
        users = self.list_users()
        if name not in users:
            users.append(name)
            _atomic_write_json(self._users_path, {"users": users})
        return users

    # -- Projects --

    @property
    def _projects_path(self) -> Path:
        return self.annotate_dir / "projects.json"

    def _registry(self) -> dict[str, dict]:
        return _read_json(self._projects_path, {"projects": {}}).get("projects", {})

    def list_projects(self) -> list[ProjectSummary]:
        summaries = []
        for name, entry in self._registry().items():
            images_dir = entry.get("images_dir", "")
            num_images = num_annotated = 0
            if Path(images_dir).is_dir():
                try:
                    images = self.list_images(name)
                except Exception:
                    # One broken project must not take down the whole listing
                    logger.exception(f"Failed to scan project '{name}' at {images_dir}")
                    images = []
                num_images = len(images)
                num_annotated = sum(1 for i in images if i.annotated)
            summaries.append(
                ProjectSummary(
                    name=name,
                    images_dir=images_dir,
                    num_images=num_images,
                    num_annotated=num_annotated,
                )
            )
        return summaries

    def create_project(self, name: str, images_dir: str | Path) -> ProjectMeta:
        images_dir = Path(images_dir).expanduser().resolve()
        if not images_dir.is_dir():
            raise FileNotFoundError(f"Images directory not found: {images_dir}")
        registry = self._registry()
        if name in registry:
            raise FileExistsError(f"Project '{name}' already exists")
        _check_stem_collisions(images_dir)

        meta = ProjectMeta(name=name, images_dir=str(images_dir))
        ann_dir = images_dir / ANNOTATIONS_SUBDIR
        project_json = ann_dir / "project.json"
        if project_json.exists():
            # Re-opening an existing annotated directory: keep its metadata
            meta = ProjectMeta(**{**_read_json(project_json), "name": name,
                                  "images_dir": str(images_dir)})
        _atomic_write_json(project_json, meta.model_dump())

        registry[name] = {"images_dir": str(images_dir)}
        _atomic_write_json(self._projects_path, {"projects": registry})
        logger.info(f"Created project '{name}' at {images_dir}")
        return meta

    def delete_project(self, name: str) -> None:
        """Unregister a project. Annotations on disk are kept."""
        registry = self._registry()
        if name not in registry:
            raise KeyError(f"Unknown project '{name}'")
        del registry[name]
        _atomic_write_json(self._projects_path, {"projects": registry})
        logger.info(f"Deleted project '{name}' (annotations kept on disk)")

    def rename_project(self, old: str, new: str) -> ProjectMeta:
        registry = self._registry()
        if old not in registry:
            raise KeyError(f"Unknown project '{old}'")
        if new in registry:
            raise FileExistsError(f"Project '{new}' already exists")
        meta = self.load_project(old)
        registry[new] = registry.pop(old)
        _atomic_write_json(self._projects_path, {"projects": registry})
        meta.name = new
        self.save_project(meta)
        return meta

    def images_dir(self, name: str) -> Path:
        registry = self._registry()
        if name not in registry:
            raise KeyError(f"Unknown project '{name}'")
        return Path(registry[name]["images_dir"])

    def _ann_dir(self, name: str) -> Path:
        return self.images_dir(name) / ANNOTATIONS_SUBDIR

    def load_project(self, name: str) -> ProjectMeta:
        data = _read_json(self._ann_dir(name) / "project.json")
        data.setdefault("name", name)
        data.setdefault("images_dir", str(self.images_dir(name)))
        return ProjectMeta(**data)

    def save_project(self, meta: ProjectMeta) -> None:
        _atomic_write_json(
            self._ann_dir(meta.name) / "project.json", meta.model_dump()
        )

    def set_labels(self, name: str, labels: list[LabelDef]) -> ProjectMeta:
        meta = self.load_project(name)
        meta.labels = labels
        self.save_project(meta)
        return meta

    def set_assignments(self, name: str, assignments: dict[str, str]) -> ProjectMeta:
        meta = self.load_project(name)
        meta.assignments = assignments
        self.save_project(meta)
        return meta

    # -- Images --

    def list_image_files(self, name: str) -> list[str]:
        """Sorted image filenames in the project directory (non-recursive)."""
        images_dir = self.images_dir(name)
        return sorted(
            p.name
            for p in images_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )

    def list_images(self, name: str) -> list[ImageInfo]:
        meta = self.load_project(name)
        cache_path = self._ann_dir(name) / "dims.json"
        cache = _read_json(cache_path)
        cache_dirty = False
        infos = []
        for filename in self.list_image_files(name):
            try:
                width, height, hit = self._cached_dims(name, filename, cache)
                cache_dirty = cache_dirty or not hit
            except OSError:
                # Corrupt/truncated file: skip it rather than failing the listing
                logger.warning(f"Skipping unreadable image: {filename}")
                continue
            doc_path = self._annotation_path(name, filename)
            num_shapes = 0
            if doc_path.exists():
                num_shapes = len(_read_json(doc_path).get("shapes", []))
            infos.append(
                ImageInfo(
                    filename=filename,
                    width=width,
                    height=height,
                    assigned_to=meta.assignments.get(filename),
                    annotated=num_shapes > 0,
                    num_shapes=num_shapes,
                )
            )
        if cache_dirty:
            _atomic_write_json(cache_path, cache)
        return infos

    def image_path(self, name: str, filename: str) -> Path:
        """Resolve an image path, rejecting anything not listed in the dir."""
        if filename not in self.list_image_files(name):
            raise FileNotFoundError(f"Image not found: {filename}")
        return self.images_dir(name) / filename

    def _cached_dims(
        self, name: str, filename: str, cache: dict
    ) -> tuple[int, int, bool]:
        """(width, height, cache_hit); updates `cache` in place on miss.

        Entries are [w, h, mtime_ns, size] so edited files are re-scanned.
        """
        stat = (self.images_dir(name) / filename).stat()
        entry = cache.get(filename)
        if entry and entry[2] == stat.st_mtime_ns and entry[3] == stat.st_size:
            return entry[0], entry[1], True
        with Image.open(self.images_dir(name) / filename) as img:
            width, height = img.size
        cache[filename] = [width, height, stat.st_mtime_ns, stat.st_size]
        return width, height, False

    def _image_dims(self, name: str, filename: str) -> tuple[int, int]:
        """Single-image (width, height) via the dims cache."""
        cache_path = self._ann_dir(name) / "dims.json"
        cache = _read_json(cache_path)
        width, height, hit = self._cached_dims(name, filename, cache)
        if not hit:
            _atomic_write_json(cache_path, cache)
        return width, height

    # -- Annotations --

    def _annotation_path(self, name: str, filename: str) -> Path:
        return self._ann_dir(name) / f"{Path(filename).stem}.json"

    def load_annotation(self, name: str, filename: str) -> LabelMeDoc:
        """Load the saved doc, or a fresh skeleton with real image dims."""
        path = self._annotation_path(name, filename)
        if path.exists():
            return LabelMeDoc(**_read_json(path))
        width, height = self._image_dims(name, filename)
        return LabelMeDoc(
            imagePath=f"../{filename}", imageHeight=height, imageWidth=width
        )

    def save_annotation(self, name: str, filename: str, doc: LabelMeDoc) -> None:
        # Ensure the doc points at the right image regardless of client input
        doc.imagePath = f"../{filename}"
        # Never persist embedded base64 image data — the image lives next door
        doc.imageData = None
        _atomic_write_json(self._annotation_path(name, filename), doc.model_dump())
