"""Tests for dataset conversion utilities."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
import yaml

from aiops.vision.dataset import (
    voc_to_yolo,
    coco_to_yolo,
    create_yolo_yaml,
    split_dataset,
)


def _make_voc_xml(path: Path, filename: str, w: int, h: int, objects: list[dict]) -> None:
    root = ET.Element("annotation")
    ET.SubElement(root, "filename").text = filename
    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(w)
    ET.SubElement(size, "height").text = str(h)
    ET.SubElement(size, "depth").text = "3"

    for obj in objects:
        o = ET.SubElement(root, "object")
        ET.SubElement(o, "name").text = obj["name"]
        bbox = ET.SubElement(o, "bndbox")
        ET.SubElement(bbox, "xmin").text = str(obj["xmin"])
        ET.SubElement(bbox, "ymin").text = str(obj["ymin"])
        ET.SubElement(bbox, "xmax").text = str(obj["xmax"])
        ET.SubElement(bbox, "ymax").text = str(obj["ymax"])

    tree = ET.ElementTree(root)
    tree.write(str(path))


class TestVocToYolo:
    def test_converts_annotations(self, tmp_path):
        voc_dir = tmp_path / "voc"
        voc_dir.mkdir()
        out_dir = tmp_path / "yolo"

        _make_voc_xml(
            voc_dir / "img1.xml", "img1.jpg", 640, 480,
            [{"name": "cat", "xmin": 100, "ymin": 50, "xmax": 300, "ymax": 250}],
        )

        voc_to_yolo(voc_dir, out_dir, classes=["cat"])

        label = (out_dir / "img1.txt").read_text().strip()
        parts = label.split()
        assert parts[0] == "0"  # class id
        assert len(parts) == 5  # cls x y w h
        # Check center x: (100+300)/2/640 = 0.3125
        assert abs(float(parts[1]) - 0.3125) < 0.001


class TestCocoToYolo:
    def test_converts_annotations(self, tmp_path):
        coco = {
            "images": [{"id": 1, "file_name": "img1.jpg", "width": 640, "height": 480}],
            "annotations": [
                {"id": 1, "image_id": 1, "category_id": 1, "bbox": [100, 50, 200, 200]},
            ],
            "categories": [{"id": 1, "name": "dog"}],
        }
        coco_file = tmp_path / "coco.json"
        coco_file.write_text(json.dumps(coco))
        out_dir = tmp_path / "yolo"

        coco_to_yolo(coco_file, out_dir)

        label = (out_dir / "img1.txt").read_text().strip()
        parts = label.split()
        assert parts[0] == "0"
        assert len(parts) == 5

        classes = (out_dir / "classes.txt").read_text().strip()
        assert classes == "dog"


class TestCreateYoloYaml:
    def test_creates_yaml(self, tmp_path):
        out = tmp_path / "dataset.yaml"
        create_yolo_yaml(tmp_path, classes=["car", "person"], output_path=out)

        config = yaml.safe_load(out.read_text())
        assert config["names"] == {0: "car", 1: "person"}
        assert config["train"] == "train/images"
        assert config["val"] == "val/images"


class TestSplitDataset:
    def test_splits_files(self, tmp_path):
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()
        out_dir = tmp_path / "split"

        for i in range(10):
            img = np.zeros((10, 10, 3), dtype=np.uint8)
            cv2.imwrite(str(images_dir / f"img_{i}.jpg"), img)
            (labels_dir / f"img_{i}.txt").write_text(f"0 0.5 0.5 0.1 0.1")

        counts = split_dataset(images_dir, labels_dir, out_dir, train_ratio=0.7, val_ratio=0.2)

        assert counts["train"] == 7
        assert counts["val"] == 2
        assert counts["test"] == 1
        assert (out_dir / "train" / "images").is_dir()
        assert (out_dir / "train" / "labels").is_dir()
