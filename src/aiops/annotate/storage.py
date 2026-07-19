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
                images = self.list_images(name)
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
        infos = []
        for filename in self.list_image_files(name):
            width, height = self._image_dims(name, filename)
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
        return infos

    def image_path(self, name: str, filename: str) -> Path:
        """Resolve an image path, rejecting anything not listed in the dir."""
        if filename not in self.list_image_files(name):
            raise FileNotFoundError(f"Image not found: {filename}")
        return self.images_dir(name) / filename

    def _image_dims(self, name: str, filename: str) -> tuple[int, int]:
        with Image.open(self.images_dir(name) / filename) as img:
            return img.size  # (width, height)

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
        _atomic_write_json(self._annotation_path(name, filename), doc.model_dump())
