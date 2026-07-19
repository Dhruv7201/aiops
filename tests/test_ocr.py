"""Tests for OCR engine adapters (logic that doesn't need the heavy deps)."""

from aiops.ocr.tesseract_engine import normalize_lang


class TestTesseractLangNormalization:
    def test_two_letter_codes_mapped(self):
        assert normalize_lang("en") == "eng"
        assert normalize_lang("de") == "deu"
        assert normalize_lang("zh") == "chi_sim"

    def test_three_letter_codes_pass_through(self):
        assert normalize_lang("eng") == "eng"
        assert normalize_lang("chi_tra") == "chi_tra"

    def test_case_insensitive(self):
        assert normalize_lang("EN") == "eng"
