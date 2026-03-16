"""EasyOCR engine adapter."""

from __future__ import annotations

from typing import Any

from aiops.core.log import get_logger
from aiops.core.types import ImageArray, OCRResult
from aiops.ocr.base import OCRBase, register_engine

logger = get_logger(__name__)


@register_engine("easyocr")
class EasyOCREngine(OCRBase):
    """EasyOCR adapter — normalizes output to unified OCRResult format."""

    def __init__(self, lang: str = "en", **kwargs: Any) -> None:
        super().__init__(lang=lang, **kwargs)
        self._reader = self._create_reader(**kwargs)

    def _create_reader(self, **kwargs: Any):
        try:
            import easyocr
        except ImportError:
            raise ImportError(
                "EasyOCR is not installed. Install with: pip install 'aiops[easyocr]'"
            )
        gpu = kwargs.pop("gpu", False)
        lang_list = kwargs.pop("lang_list", [self.lang])
        return easyocr.Reader(lang_list, gpu=gpu, **kwargs)

    def _raw_detect(self, image: ImageArray) -> list[OCRResult]:
        raw = self._reader.readtext(image)
        results: list[OCRResult] = []
        for bbox_raw, text, score in raw:
            # EasyOCR returns [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            bbox = [list(map(float, pt)) for pt in bbox_raw]
            results.append(OCRResult(text=text, score=float(score), bbox=bbox))
        return results
