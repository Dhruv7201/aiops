"""PaddleOCR engine adapter. Supports both PaddleOCR 2.x and 3.x."""

from __future__ import annotations

from typing import Any

from aiops.core.log import get_logger
from aiops.core.types import ImageArray, OCRResult
from aiops.ocr.base import OCRBase, register_engine

logger = get_logger(__name__)


def _detect_paddle_version() -> int:
    """Detect PaddleOCR major version (2 or 3)."""
    try:
        import paddleocr

        version = getattr(paddleocr, "__version__", getattr(paddleocr, "VERSION", "2.0.0"))
        major = int(str(version).split(".")[0])
        logger.debug(f"PaddleOCR version detected: {version} (major={major})")
        return major
    except ImportError:
        raise ImportError(
            "PaddleOCR is not installed. Install with: pip install 'aiops[paddle]'"
        )


@register_engine("paddle")
class PaddleOCREngine(OCRBase):
    """PaddleOCR adapter with auto version detection."""

    def __init__(self, lang: str = "en", **kwargs: Any) -> None:
        super().__init__(lang=lang, **kwargs)
        self._version = _detect_paddle_version()
        self._ocr = self._create_engine(**kwargs)

    def _create_engine(self, **kwargs: Any):
        from paddleocr import PaddleOCR

        default_kwargs = {
            "use_angle_cls": True,
            "lang": self.lang,
            "show_log": False,
        }
        default_kwargs.update(kwargs)
        return PaddleOCR(**default_kwargs)

    def _raw_detect(self, image: ImageArray) -> list[OCRResult]:
        if self._version >= 3:
            return self._parse_v3(image)
        return self._parse_v2(image)

    def _parse_v2(self, image: ImageArray) -> list[OCRResult]:
        result = self._ocr.ocr(image, cls=True)
        results: list[OCRResult] = []
        if not result or not result[0]:
            return results
        for line in result[0]:
            bbox = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            text = line[1][0]
            score = float(line[1][1])
            results.append(OCRResult(text=text, score=score, bbox=bbox))
        return results

    def _parse_v3(self, image: ImageArray) -> list[OCRResult]:
        result = self._ocr.ocr(image, cls=True)
        results: list[OCRResult] = []
        if not result or not result[0]:
            return results
        for line in result[0]:
            # PaddleOCR 3.x may return a different structure
            # but commonly still returns [[bbox], (text, score)]
            if isinstance(line, dict):
                bbox = line.get("boxes", line.get("bbox", []))
                text = line.get("text", line.get("rec_text", ""))
                score = float(line.get("score", line.get("rec_score", 0.0)))
            else:
                bbox = line[0]
                text = line[1][0]
                score = float(line[1][1])
            results.append(OCRResult(text=text, score=score, bbox=bbox))
        return results
