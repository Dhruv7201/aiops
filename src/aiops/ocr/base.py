"""Unified OCR interface with pluggable backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from aiops.core.log import get_logger
from aiops.core.plugin import PluginRegistry
from aiops.core.types import BBox, ImageArray, OCREngine, OCRResult

logger = get_logger(__name__)

# Global registry for OCR engines
_ocr_registry = PluginRegistry("ocr_engine")


def register_engine(name: str):
    """Decorator to register an OCR engine class."""

    def wrapper(cls):
        _ocr_registry.register(name, cls)
        return cls

    return wrapper


class OCRBase(ABC):
    """Abstract base class for OCR engines."""

    def __init__(self, lang: str = "en", **kwargs: Any) -> None:
        self.lang = lang
        self._kwargs = kwargs

    @abstractmethod
    def _raw_detect(self, image: ImageArray) -> list[OCRResult]:
        """Run engine-specific detection. Returns full OCRResult list."""
        ...

    def detect(
        self,
        image: ImageArray | str | Path,
        *,
        return_text: bool = True,
        return_score: bool = True,
        return_bbox: bool = True,
    ) -> list[dict]:
        """Run OCR and return results with requested fields.

        Args:
            image: numpy array (BGR), or path to image file.
            return_text: include detected text in output.
            return_score: include confidence score in output.
            return_bbox: include bounding box in output.

        Returns:
            List of dicts with requested fields.
        """
        img = self._load_image(image)
        results = self._raw_detect(img)
        return [
            r.to_dict(text=return_text, score=return_score, bbox=return_bbox)
            for r in results
        ]

    @staticmethod
    def _load_image(image: ImageArray | str | Path) -> ImageArray:
        if isinstance(image, (str, Path)):
            path = str(image)
            img = cv2.imread(path)
            if img is None:
                raise FileNotFoundError(f"Cannot read image: {path}")
            return img
        return image


class OCR:
    """Unified OCR facade.

    Usage:
        ocr = OCR(engine="paddle")
        results = ocr.detect(image, return_text=True, return_score=True)
    """

    def __init__(self, engine: str = "paddle", lang: str = "en", **kwargs: Any) -> None:
        self.engine_name = engine
        # Lazy-register built-in engines on first use
        _ensure_builtins_registered()
        engine_cls = _ocr_registry.get(engine)
        self._engine: OCRBase = engine_cls(lang=lang, **kwargs)
        logger.info(f"OCR initialized with engine={engine}, lang={lang}")

    def detect(
        self,
        image: ImageArray | str | Path,
        *,
        return_text: bool = True,
        return_score: bool = True,
        return_bbox: bool = True,
    ) -> list[dict]:
        return self._engine.detect(
            image,
            return_text=return_text,
            return_score=return_score,
            return_bbox=return_bbox,
        )

    @staticmethod
    def available_engines() -> list[str]:
        _ensure_builtins_registered()
        return _ocr_registry.keys()


_builtins_registered = False


def _ensure_builtins_registered():
    global _builtins_registered
    if _builtins_registered:
        return
    _builtins_registered = True
    # Import engine modules to trigger @register_engine decorators
    from aiops.ocr import paddle_engine, easy_engine, tesseract_engine  # noqa: F401
