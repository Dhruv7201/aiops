"""Shared test fixtures."""

from pathlib import Path

import cv2
import numpy as np
import pytest


@pytest.fixture
def sample_image() -> np.ndarray:
    """Create a simple test image (white text on black background)."""
    img = np.zeros((100, 300, 3), dtype=np.uint8)
    cv2.putText(img, "Hello World", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
    return img


@pytest.fixture
def sample_image_path(tmp_path: Path, sample_image: np.ndarray) -> Path:
    """Save sample image to a temp file and return its path."""
    path = tmp_path / "test_image.png"
    cv2.imwrite(str(path), sample_image)
    return path


@pytest.fixture
def tmp_dataset(tmp_path: Path, sample_image: np.ndarray) -> Path:
    """Create a minimal dataset structure for testing."""
    dataset = tmp_path / "dataset"
    train_images = dataset / "train" / "images"
    val_images = dataset / "val" / "images"
    train_images.mkdir(parents=True)
    val_images.mkdir(parents=True)

    for i in range(4):
        cv2.imwrite(str(train_images / f"img_{i}.png"), sample_image)
    for i in range(2):
        cv2.imwrite(str(val_images / f"img_{i}.png"), sample_image)

    return dataset
