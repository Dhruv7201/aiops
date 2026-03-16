"""Shared types and data models used across the library."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


# -- Image types --

ImageArray = NDArray[np.uint8]
"""HxWxC uint8 numpy array (BGR by default, matching OpenCV)."""

BBox = list[list[float]]
"""4-point bounding box: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]."""


@dataclass(slots=True)
class OCRResult:
    """Single OCR detection result with optional fields."""

    text: str | None = None
    score: float | None = None
    bbox: BBox | None = None

    def to_dict(self, *, text: bool = True, score: bool = True, bbox: bool = True) -> dict:
        out: dict[str, Any] = {}
        if text and self.text is not None:
            out["text"] = self.text
        if score and self.score is not None:
            out["score"] = self.score
        if bbox and self.bbox is not None:
            out["bbox"] = self.bbox
        return out


@dataclass(slots=True)
class DetectionResult:
    """Single object detection result."""

    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2] xyxy format
    mask: NDArray | None = None


@dataclass(slots=True)
class ROI:
    """Region of interest on an image."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def crop(self, image: ImageArray) -> ImageArray:
        return image[self.y1 : self.y2, self.x1 : self.x2]

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


class OCREngine(StrEnum):
    PADDLE = "paddle"
    EASYOCR = "easyocr"
    TESSERACT = "tesseract"


class DBBackend(StrEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MSSQL = "mssql"
    MONGODB = "mongodb"
    REDIS = "redis"


class BackendFramework(StrEnum):
    FASTAPI = "fastapi"
    FLASK = "flask"
    DJANGO = "django"


@dataclass
class DatasetSplit:
    """Paths for a dataset split."""

    images_dir: Path
    labels_dir: Path
    split: str = "train"
    classes: list[str] = field(default_factory=list)
