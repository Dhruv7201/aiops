"""Tesseract OCR engine adapter."""

from __future__ import annotations

from typing import Any

import cv2

from aiops.core.log import get_logger
from aiops.core.types import ImageArray, OCRResult
from aiops.ocr.base import OCRBase, register_engine

logger = get_logger(__name__)


@register_engine("tesseract")
class TesseractEngine(OCRBase):
    """Tesseract adapter — normalizes output to unified OCRResult format."""

    def __init__(self, lang: str = "eng", **kwargs: Any) -> None:
        # Tesseract uses 3-letter codes like 'eng', not 'en'
        super().__init__(lang=lang, **kwargs)
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            raise ImportError(
                "pytesseract is not installed. Install with: pip install 'aiops[tesseract]'"
            )

    def _raw_detect(self, image: ImageArray) -> list[OCRResult]:
        import pytesseract

        # Convert BGR to RGB for Tesseract
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        data = pytesseract.image_to_data(
            rgb, lang=self.lang, output_type=pytesseract.Output.DICT
        )

        results: list[OCRResult] = []
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])

            if not text or conf < 0:
                continue

            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            # Convert to 4-point bbox format
            bbox = [
                [float(x), float(y)],
                [float(x + w), float(y)],
                [float(x + w), float(y + h)],
                [float(x), float(y + h)],
            ]
            score = conf / 100.0  # Tesseract returns 0-100

            results.append(OCRResult(text=text, score=score, bbox=bbox))

        return results
