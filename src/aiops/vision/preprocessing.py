"""Image preprocessing helpers for CV pipelines."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from aiops.core.types import ImageArray


class ImagePreprocessor:
    """Chainable image preprocessing pipeline.

    Usage:
        preprocessor = ImagePreprocessor()
        result = (
            preprocessor
            .load("image.png")
            .resize(640, 480)
            .grayscale()
            .threshold()
            .result()
        )
    """

    def __init__(self, image: ImageArray | None = None) -> None:
        self._image: ImageArray | None = image

    def load(self, path: str | Path) -> ImagePreprocessor:
        img = cv2.imread(str(path))
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {path}")
        self._image = img
        return self

    def result(self) -> ImageArray:
        if self._image is None:
            raise ValueError("No image loaded")
        return self._image

    def save(self, path: str | Path) -> ImagePreprocessor:
        cv2.imwrite(str(path), self.result())
        return self

    def resize(self, width: int, height: int) -> ImagePreprocessor:
        self._image = cv2.resize(self.result(), (width, height))
        return self

    def scale(self, factor: float) -> ImagePreprocessor:
        img = self.result()
        h, w = img.shape[:2]
        self._image = cv2.resize(img, (int(w * factor), int(h * factor)))
        return self

    def grayscale(self) -> ImagePreprocessor:
        img = self.result()
        if len(img.shape) == 3:
            self._image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return self

    def threshold(
        self, thresh: int = 127, maxval: int = 255, method: int = cv2.THRESH_BINARY
    ) -> ImagePreprocessor:
        _, self._image = cv2.threshold(self.result(), thresh, maxval, method)
        return self

    def adaptive_threshold(
        self,
        maxval: int = 255,
        method: int = cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        block_size: int = 11,
        c: int = 2,
    ) -> ImagePreprocessor:
        img = self.result()
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        self._image = cv2.adaptiveThreshold(img, maxval, method, cv2.THRESH_BINARY, block_size, c)
        return self

    def blur(self, ksize: int = 5) -> ImagePreprocessor:
        self._image = cv2.GaussianBlur(self.result(), (ksize, ksize), 0)
        return self

    def denoise(self, strength: int = 10) -> ImagePreprocessor:
        img = self.result()
        if len(img.shape) == 3:
            self._image = cv2.fastNlMeansDenoisingColored(img, None, strength, strength)
        else:
            self._image = cv2.fastNlMeansDenoising(img, None, strength)
        return self

    def sharpen(self) -> ImagePreprocessor:
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        self._image = cv2.filter2D(self.result(), -1, kernel)
        return self

    def rotate(self, angle: float, center: tuple[int, int] | None = None) -> ImagePreprocessor:
        img = self.result()
        h, w = img.shape[:2]
        c = center or (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(c, angle, 1.0)
        self._image = cv2.warpAffine(img, matrix, (w, h))
        return self

    def deskew(self) -> ImagePreprocessor:
        """Auto-deskew using Hough line detection."""
        img = self.result()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)

        if lines is None:
            return self

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(angle) < 45:
                angles.append(angle)

        if angles:
            median_angle = float(np.median(angles))
            self.rotate(-median_angle)

        return self

    def normalize(self) -> ImagePreprocessor:
        """Normalize pixel values to 0-255 range."""
        img = self.result()
        self._image = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        return self

    def pad(self, top: int = 0, bottom: int = 0, left: int = 0, right: int = 0, color: int = 0) -> ImagePreprocessor:
        self._image = cv2.copyMakeBorder(
            self.result(), top, bottom, left, right, cv2.BORDER_CONSTANT, value=color
        )
        return self
