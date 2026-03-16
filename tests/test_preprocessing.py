"""Tests for image preprocessing pipeline."""

import numpy as np

from aiops.vision.preprocessing import ImagePreprocessor


class TestImagePreprocessor:
    def test_load_and_result(self, sample_image_path):
        img = ImagePreprocessor().load(sample_image_path).result()
        assert img.shape[2] == 3

    def test_load_missing_raises(self):
        try:
            ImagePreprocessor().load("/nonexistent/image.png")
            assert False, "Should have raised"
        except FileNotFoundError:
            pass

    def test_result_without_load_raises(self):
        try:
            ImagePreprocessor().result()
            assert False, "Should have raised"
        except ValueError:
            pass

    def test_resize(self, sample_image):
        img = ImagePreprocessor(sample_image).resize(100, 50).result()
        assert img.shape == (50, 100, 3)

    def test_scale(self, sample_image):
        img = ImagePreprocessor(sample_image).scale(0.5).result()
        h, w = sample_image.shape[:2]
        assert img.shape[0] == h // 2
        assert img.shape[1] == w // 2

    def test_grayscale(self, sample_image):
        img = ImagePreprocessor(sample_image).grayscale().result()
        assert len(img.shape) == 2

    def test_grayscale_idempotent(self, sample_image):
        img = ImagePreprocessor(sample_image).grayscale().grayscale().result()
        assert len(img.shape) == 2

    def test_threshold(self, sample_image):
        img = ImagePreprocessor(sample_image).grayscale().threshold(thresh=127).result()
        unique = np.unique(img)
        assert len(unique) <= 2  # binary

    def test_adaptive_threshold(self, sample_image):
        img = (
            ImagePreprocessor(sample_image)
            .grayscale()
            .adaptive_threshold(block_size=11, c=2)
            .result()
        )
        unique = np.unique(img)
        assert len(unique) <= 2

    def test_blur(self, sample_image):
        img = ImagePreprocessor(sample_image).blur(ksize=5).result()
        assert img.shape == sample_image.shape

    def test_sharpen(self, sample_image):
        img = ImagePreprocessor(sample_image).sharpen().result()
        assert img.shape == sample_image.shape

    def test_rotate(self, sample_image):
        img = ImagePreprocessor(sample_image).rotate(45).result()
        assert img.shape == sample_image.shape

    def test_normalize(self, sample_image):
        img = ImagePreprocessor(sample_image).normalize().result()
        assert img.max() == 255 or img.max() == 0

    def test_pad(self, sample_image):
        img = ImagePreprocessor(sample_image).pad(top=10, bottom=10, left=5, right=5).result()
        h, w = sample_image.shape[:2]
        assert img.shape[0] == h + 20
        assert img.shape[1] == w + 10

    def test_save(self, sample_image, tmp_path):
        out = tmp_path / "saved.png"
        ImagePreprocessor(sample_image).save(out)
        assert out.exists()

    def test_chain(self, sample_image):
        img = (
            ImagePreprocessor(sample_image)
            .resize(200, 100)
            .blur(ksize=3)
            .grayscale()
            .normalize()
            .result()
        )
        assert img.shape == (100, 200)

    def test_denoise(self, sample_image):
        img = ImagePreprocessor(sample_image).denoise(strength=10).result()
        assert img.shape == sample_image.shape

    def test_denoise_grayscale(self, sample_image):
        img = ImagePreprocessor(sample_image).grayscale().denoise(strength=10).result()
        assert len(img.shape) == 2
