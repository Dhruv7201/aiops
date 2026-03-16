"""YOLO detection, training, and inference utilities wrapping Ultralytics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from aiops.core.log import get_logger
from aiops.core.types import DetectionResult, ImageArray

logger = get_logger(__name__)


class YOLODetector:
    """Unified YOLO interface for detection, training, and evaluation.

    Usage:
        detector = YOLODetector(model="yolov8n.pt")
        results = detector.predict(image)
        detector.train(dataset="dataset.yaml", epochs=50)
    """

    def __init__(self, model: str = "yolov8n.pt", device: str = "cpu") -> None:
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError(
                "Ultralytics is not installed. Install with: pip install 'aiops[yolo]'"
            )
        self.model_path = model
        self.device = device
        self._model = YOLO(model)
        logger.info(f"YOLO model loaded: {model} on {device}")

    def predict(
        self,
        image: ImageArray | str | Path,
        conf: float = 0.25,
        iou: float = 0.45,
        classes: list[int] | None = None,
        **kwargs: Any,
    ) -> list[DetectionResult]:
        """Run inference on an image.

        Args:
            image: numpy array (BGR) or path to image.
            conf: confidence threshold.
            iou: IoU threshold for NMS.
            classes: filter by class IDs.

        Returns:
            List of DetectionResult objects.
        """
        results = self._model.predict(
            source=image,
            conf=conf,
            iou=iou,
            classes=classes,
            device=self.device,
            verbose=False,
            **kwargs,
        )

        detections: list[DetectionResult] = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                bbox = boxes.xyxy[i].cpu().numpy().tolist()
                conf_val = float(boxes.conf[i].cpu())
                cls_id = int(boxes.cls[i].cpu())
                cls_name = r.names.get(cls_id, str(cls_id))
                mask = None
                if r.masks is not None:
                    mask = r.masks.data[i].cpu().numpy()
                detections.append(
                    DetectionResult(
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=conf_val,
                        bbox=bbox,
                        mask=mask,
                    )
                )
        return detections

    def train(
        self,
        dataset: str | Path,
        epochs: int = 50,
        imgsz: int = 640,
        batch: int = 16,
        name: str = "train",
        **kwargs: Any,
    ) -> Any:
        """Train the YOLO model.

        Args:
            dataset: path to dataset YAML file.
            epochs: number of training epochs.
            imgsz: input image size.
            batch: batch size.
            name: experiment name.

        Returns:
            Ultralytics training results.
        """
        logger.info(f"Starting YOLO training: {dataset}, epochs={epochs}")
        return self._model.train(
            data=str(dataset),
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            name=name,
            device=self.device,
            **kwargs,
        )

    def evaluate(self, dataset: str | Path | None = None, **kwargs: Any) -> Any:
        """Evaluate model on validation set."""
        logger.info("Running YOLO evaluation")
        return self._model.val(data=str(dataset) if dataset else None, device=self.device, **kwargs)

    def export(self, format: str = "onnx", **kwargs: Any) -> Path:
        """Export model to specified format."""
        logger.info(f"Exporting model to {format}")
        path = self._model.export(format=format, **kwargs)
        return Path(path)

    def benchmark(
        self,
        image: ImageArray | str | Path,
        runs: int = 100,
    ) -> dict[str, float]:
        """Benchmark inference speed.

        Returns:
            Dict with avg_ms, fps, min_ms, max_ms.
        """
        import time

        times: list[float] = []
        for _ in range(runs):
            start = time.perf_counter()
            self.predict(image)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg = np.mean(times)
        return {
            "avg_ms": float(avg),
            "fps": 1000.0 / avg,
            "min_ms": float(np.min(times)),
            "max_ms": float(np.max(times)),
            "runs": runs,
        }

    def visualize(
        self,
        image: ImageArray | str | Path,
        detections: list[DetectionResult] | None = None,
        conf: float = 0.25,
    ) -> ImageArray:
        """Draw detection results on an image.

        If detections not provided, runs prediction first.
        """
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
        else:
            img = image.copy()

        if detections is None:
            detections = self.predict(img, conf=conf)

        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det.bbox]
            color = _class_color(det.class_id)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            label = f"{det.class_name} {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
            cv2.putText(img, label, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return img


def _class_color(class_id: int) -> tuple[int, int, int]:
    """Generate a deterministic color for a class ID."""
    np.random.seed(class_id + 42)
    return tuple(int(c) for c in np.random.randint(50, 255, 3))
