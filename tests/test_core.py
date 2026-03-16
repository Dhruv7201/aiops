"""Tests for core module: config, logging, plugin registry, types."""

import logging

from aiops.core.config import Settings, get_settings
from aiops.core.log import get_logger
from aiops.core.plugin import PluginRegistry
from aiops.core.types import OCRResult, DetectionResult, ROI, OCREngine, BackendFramework


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.debug is False
        assert s.log_level == "INFO"
        assert s.ocr_engine == "paddle"

    def test_get_settings_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestLogger:
    def test_returns_logger(self):
        log = get_logger("test")
        assert isinstance(log, logging.Logger)
        assert log.name == "test"

    def test_custom_level(self):
        log = get_logger("test_debug", level="DEBUG")
        assert log.level == logging.DEBUG


class TestPluginRegistry:
    def test_register_and_get(self):
        reg = PluginRegistry("test")
        reg.register("foo", lambda: "bar")
        assert reg.get("foo")() == "bar"

    def test_unknown_key_raises(self):
        reg = PluginRegistry("test")
        try:
            reg.get("missing")
            assert False, "Should have raised KeyError"
        except KeyError:
            pass

    def test_create(self):
        reg = PluginRegistry("test")
        reg.register("adder", lambda a, b: a + b)
        assert reg.create("adder", 2, 3) == 5

    def test_keys(self):
        reg = PluginRegistry("test")
        reg.register("a", lambda: None)
        reg.register("b", lambda: None)
        assert sorted(reg.keys()) == ["a", "b"]

    def test_contains(self):
        reg = PluginRegistry("test")
        reg.register("x", lambda: None)
        assert "x" in reg
        assert "y" not in reg


class TestOCRResult:
    def test_to_dict_all(self):
        r = OCRResult(text="hello", score=0.95, bbox=[[0, 0], [1, 0], [1, 1], [0, 1]])
        d = r.to_dict(text=True, score=True, bbox=True)
        assert d == {"text": "hello", "score": 0.95, "bbox": [[0, 0], [1, 0], [1, 1], [0, 1]]}

    def test_to_dict_text_only(self):
        r = OCRResult(text="hello", score=0.95, bbox=[[0, 0]])
        d = r.to_dict(text=True, score=False, bbox=False)
        assert d == {"text": "hello"}

    def test_to_dict_empty(self):
        r = OCRResult()
        d = r.to_dict()
        assert d == {}


class TestDetectionResult:
    def test_fields(self):
        d = DetectionResult(class_id=0, class_name="cat", confidence=0.9, bbox=[10, 20, 100, 200])
        assert d.class_name == "cat"
        assert d.mask is None


class TestROI:
    def test_dimensions(self):
        roi = ROI(x1=10, y1=20, x2=110, y2=220)
        assert roi.width == 100
        assert roi.height == 200

    def test_as_tuple(self):
        roi = ROI(x1=1, y1=2, x2=3, y2=4)
        assert roi.as_tuple() == (1, 2, 3, 4)

    def test_crop(self, sample_image):
        roi = ROI(x1=10, y1=10, x2=50, y2=50)
        cropped = roi.crop(sample_image)
        assert cropped.shape == (40, 40, 3)


class TestEnums:
    def test_ocr_engine_values(self):
        assert OCREngine.PADDLE == "paddle"
        assert OCREngine.EASYOCR == "easyocr"
        assert OCREngine.TESSERACT == "tesseract"

    def test_backend_framework_values(self):
        assert BackendFramework.FASTAPI == "fastapi"
        assert BackendFramework.FLASK == "flask"
        assert BackendFramework.DJANGO == "django"
