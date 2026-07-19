"""Pydantic models for the annotation tool — LabelMe-compatible schema.

No fastapi imports here so pure logic stays importable without web deps.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

LABELME_VERSION = "5.4.1"

DEFAULT_LABEL_COLORS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080",
]


class LabelDef(BaseModel):
    """A label class with its display color."""

    name: str
    color: str = "#e6194b"

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label name cannot be empty")
        return v


ShapeType = Literal["rectangle", "polygon", "circle", "line", "point", "linestrip"]

# (min_points, max_points or None) per shape type
_POINT_RULES: dict[str, tuple[int, int | None]] = {
    "rectangle": (2, 2),
    "polygon": (3, None),
    "circle": (2, 2),
    "line": (2, 2),
    "point": (1, 1),
    "linestrip": (2, None),
}


class Shape(BaseModel):
    """Single annotation shape, matching LabelMe's shape schema.

    The editor only creates rectangles and polygons, but the other LabelMe
    types are accepted (and rendered read-only) so external docs load.
    """

    label: str
    points: list[list[float]]
    shape_type: ShapeType = "rectangle"
    group_id: int | None = None
    description: str = ""
    flags: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_points(self) -> Shape:
        lo, hi = _POINT_RULES[self.shape_type]
        if len(self.points) < lo or (hi is not None and len(self.points) > hi):
            bound = f"exactly {lo}" if lo == hi else f"at least {lo}"
            raise ValueError(f"{self.shape_type} must have {bound} points")
        for pt in self.points:
            if len(pt) != 2:
                raise ValueError("each point must be [x, y]")
        return self


class LabelMeDoc(BaseModel):
    """Per-image annotation document, serialized verbatim as LabelMe JSON."""

    version: str = LABELME_VERSION
    flags: dict[str, Any] = Field(default_factory=dict)
    shapes: list[Shape] = Field(default_factory=list)
    imagePath: str = ""
    # LabelMe embeds the image as base64 by default; accept it so existing
    # annotation dirs load, but the store strips it on save to keep files lean.
    imageData: str | None = None
    imageHeight: int = 0
    imageWidth: int = 0


class ProjectMeta(BaseModel):
    """Project metadata stored in <images_dir>/.annotations/project.json."""

    name: str
    images_dir: str = ""
    labels: list[LabelDef] = Field(default_factory=list)
    users: list[str] = Field(default_factory=list)
    assignments: dict[str, str] = Field(default_factory=dict)


class ProjectSummary(BaseModel):
    """Project list entry with progress counts."""

    name: str
    images_dir: str
    num_images: int = 0
    num_annotated: int = 0


class ImageInfo(BaseModel):
    """Image listing entry with annotation status."""

    filename: str
    width: int
    height: int
    assigned_to: str | None = None
    annotated: bool = False
    num_shapes: int = 0


# -- Request models --


class CreateUserRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user name cannot be empty")
        return v


class CreateProjectRequest(BaseModel):
    name: str
    images_dir: str

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = v.strip()
        if not v or "/" in v or "\\" in v:
            raise ValueError("invalid project name")
        return v


class RenameProjectRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = v.strip()
        if not v or "/" in v or "\\" in v:
            raise ValueError("invalid project name")
        return v


class SetLabelsRequest(BaseModel):
    labels: list[LabelDef]


class AssignRequest(BaseModel):
    """Bulk-assign images among users."""

    users: list[str]
    mode: Literal["round_robin"] = "round_robin"
    keep_existing: bool = True


class ReassignRequest(BaseModel):
    """Manually assign a single image to a user (empty user = unassign)."""

    filename: str
    user: str = ""


class ExportRequest(BaseModel):
    """Export annotated images into train/val(/test) splits."""

    output_dir: str
    format: str = "labelme"
    train_ratio: float = 0.7
    val_ratio: float = 0.2
    test_ratio: float = 0.1
    seed: int | None = None

    @model_validator(mode="after")
    def _check_ratios(self) -> ExportRequest:
        for name, r in (
            ("train_ratio", self.train_ratio),
            ("val_ratio", self.val_ratio),
            ("test_ratio", self.test_ratio),
        ):
            if not 0.0 <= r <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        total = self.train_ratio + self.val_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"ratios must sum to 1.0 (got {total:.3f})")
        return self


class ExportResult(BaseModel):
    output_dir: str
    counts: dict[str, int]
