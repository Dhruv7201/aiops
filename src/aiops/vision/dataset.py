"""Dataset preparation and conversion utilities for YOLO and other formats."""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import yaml

from aiops.core.log import get_logger

logger = get_logger(__name__)


def voc_to_yolo(
    voc_dir: str | Path,
    output_dir: str | Path,
    classes: list[str] | None = None,
) -> Path:
    """Convert Pascal VOC XML annotations to YOLO format.

    Args:
        voc_dir: directory containing .xml annotation files.
        output_dir: where to write YOLO .txt label files.
        classes: ordered class list. Auto-detected if None.

    Returns:
        Path to output directory.
    """
    voc_dir = Path(voc_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if classes is None:
        classes = _detect_voc_classes(voc_dir)
        logger.info(f"Auto-detected classes: {classes}")

    class_map = {name: idx for idx, name in enumerate(classes)}
    count = 0

    for xml_file in sorted(voc_dir.glob("*.xml")):
        tree = ET.parse(xml_file)
        root = tree.getroot()
        size = root.find("size")
        w = int(size.findtext("width", "1"))
        h = int(size.findtext("height", "1"))

        lines = []
        for obj in root.iter("object"):
            cls_name = obj.findtext("name", "")
            if cls_name not in class_map:
                continue
            cls_id = class_map[cls_name]
            bbox = obj.find("bndbox")
            xmin = float(bbox.findtext("xmin", "0"))
            ymin = float(bbox.findtext("ymin", "0"))
            xmax = float(bbox.findtext("xmax", "0"))
            ymax = float(bbox.findtext("ymax", "0"))

            x_center = (xmin + xmax) / 2 / w
            y_center = (ymin + ymax) / 2 / h
            bw = (xmax - xmin) / w
            bh = (ymax - ymin) / h
            lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {bw:.6f} {bh:.6f}")

        label_file = output_dir / f"{xml_file.stem}.txt"
        label_file.write_text("\n".join(lines))
        count += 1

    logger.info(f"Converted {count} VOC annotations to YOLO format in {output_dir}")
    return output_dir


def coco_to_yolo(
    coco_json: str | Path,
    output_dir: str | Path,
) -> Path:
    """Convert COCO JSON annotations to YOLO format.

    Args:
        coco_json: path to COCO annotation JSON file.
        output_dir: where to write YOLO .txt label files.

    Returns:
        Path to output directory.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(coco_json) as f:
        coco = json.load(f)

    # Build image id -> info map
    images = {img["id"]: img for img in coco["images"]}
    # Build category id -> index map
    categories = {cat["id"]: idx for idx, cat in enumerate(coco["categories"])}

    # Group annotations by image
    image_annotations: dict[int, list] = {}
    for ann in coco["annotations"]:
        image_annotations.setdefault(ann["image_id"], []).append(ann)

    for img_id, img_info in images.items():
        w, h = img_info["width"], img_info["height"]
        lines = []
        for ann in image_annotations.get(img_id, []):
            cls_id = categories[ann["category_id"]]
            x, y, bw, bh = ann["bbox"]  # COCO: [x, y, width, height]
            x_center = (x + bw / 2) / w
            y_center = (y + bh / 2) / h
            lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {bw / w:.6f} {bh / h:.6f}")

        stem = Path(img_info["file_name"]).stem
        label_file = output_dir / f"{stem}.txt"
        label_file.write_text("\n".join(lines))

    # Write classes file
    class_names = [cat["name"] for cat in sorted(coco["categories"], key=lambda c: categories[c["id"]])]
    (output_dir / "classes.txt").write_text("\n".join(class_names))

    logger.info(f"Converted COCO annotations to YOLO format in {output_dir}")
    return output_dir


def create_yolo_yaml(
    dataset_dir: str | Path,
    classes: list[str],
    output_path: str | Path = "dataset.yaml",
    train_dir: str = "train/images",
    val_dir: str = "val/images",
    test_dir: str | None = None,
) -> Path:
    """Generate a YOLO dataset YAML config file.

    Args:
        dataset_dir: root dataset directory.
        classes: list of class names.
        output_path: where to write the YAML file.
        train_dir: relative path to training images.
        val_dir: relative path to validation images.
        test_dir: optional relative path to test images.
    """
    dataset_dir = Path(dataset_dir).resolve()
    config = {
        "path": str(dataset_dir),
        "train": train_dir,
        "val": val_dir,
        "names": {i: name for i, name in enumerate(classes)},
    }
    if test_dir:
        config["test"] = test_dir

    output = Path(output_path)
    output.write_text(yaml.dump(config, default_flow_style=False))
    logger.info(f"YOLO dataset YAML written to {output}")
    return output


def split_dataset(
    images_dir: str | Path,
    labels_dir: str | Path,
    output_dir: str | Path,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
) -> dict[str, int]:
    """Split a dataset into train/val/test directories.

    Returns:
        Dict with split counts.
    """
    images_dir = Path(images_dir)
    labels_dir = Path(labels_dir)
    output_dir = Path(output_dir)

    image_files = sorted(
        f for f in images_dir.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".tif")
    )

    import random
    random.shuffle(image_files)

    n = len(image_files)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    splits = {
        "train": image_files[:train_end],
        "val": image_files[train_end:val_end],
        "test": image_files[val_end:],
    }

    counts = {}
    for split_name, files in splits.items():
        img_out = output_dir / split_name / "images"
        lbl_out = output_dir / split_name / "labels"
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        for img_file in files:
            shutil.copy2(img_file, img_out / img_file.name)
            label_file = labels_dir / f"{img_file.stem}.txt"
            if label_file.exists():
                shutil.copy2(label_file, lbl_out / label_file.name)

        counts[split_name] = len(files)

    logger.info(f"Dataset split: {counts}")
    return counts


def _detect_voc_classes(voc_dir: Path) -> list[str]:
    classes = set()
    for xml_file in voc_dir.glob("*.xml"):
        tree = ET.parse(xml_file)
        for obj in tree.getroot().iter("object"):
            classes.add(obj.findtext("name", ""))
    return sorted(classes)
