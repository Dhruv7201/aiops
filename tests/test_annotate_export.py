"""Tests for dataset splitting and the LabelMe/YOLO/COCO exporters."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from aiops.annotate.export import run_export, split_files
from aiops.annotate.models import ExportRequest, LabelDef, LabelMeDoc, Shape
from aiops.annotate.storage import ProjectStore

FILES = [f"img_{i:02d}.png" for i in range(10)]


class TestSplitFiles:
    def test_three_way_ratios(self):
        splits = split_files(FILES, 0.7, 0.2, 0.1, seed=42)
        assert len(splits["train"]) == 7
        assert len(splits["val"]) == 2
        assert len(splits["test"]) == 1
        all_files = splits["train"] + splits["val"] + splits["test"]
        assert sorted(all_files) == FILES

    def test_two_way_no_test(self):
        splits = split_files(FILES, 0.8, 0.2, 0.0, seed=1)
        assert "test" not in splits
        assert len(splits["train"]) == 8
        assert len(splits["val"]) == 2

    def test_seed_deterministic(self):
        assert split_files(FILES, seed=7) == split_files(FILES, seed=7)

    def test_different_seeds_differ(self):
        a = split_files(FILES, seed=1)
        b = split_files(FILES, seed=2)
        assert a != b  # 10! permutations — collision effectively impossible


class TestRunExport:
    @pytest.fixture
    def project(self, tmp_path: Path) -> tuple[ProjectStore, Path]:
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        img = np.zeros((40, 60, 3), dtype=np.uint8)
        for i in range(5):
            cv2.imwrite(str(images_dir / f"img_{i}.png"), img)

        store = ProjectStore(tmp_path / "annotate")
        store.create_project("demo", images_dir)
        # Annotate 4 of 5 images
        for i in range(4):
            store.save_annotation(
                "demo",
                f"img_{i}.png",
                LabelMeDoc(
                    shapes=[Shape(label="cat", points=[[0, 0], [10, 10]])],
                    imageHeight=40,
                    imageWidth=60,
                ),
            )
        return store, tmp_path

    def test_export_labelme(self, project: tuple[ProjectStore, Path]):
        store, tmp_path = project
        out = tmp_path / "export"
        result = run_export(
            store,
            "demo",
            ExportRequest(
                output_dir=str(out),
                train_ratio=0.5,
                val_ratio=0.25,
                test_ratio=0.25,
                seed=0,
            ),
        )
        # only 4 annotated images exported
        assert sum(result.counts.values()) == 4
        for split, count in result.counts.items():
            images = list((out / split / "images").iterdir())
            labels = list((out / split / "labels").iterdir())
            assert len(images) == count
            assert len(labels) == count
            # imagePath rewritten to sibling images dir
            doc = json.loads(labels[0].read_text())
            assert doc["imagePath"] == f"../images/{labels[0].stem}.png"

    def test_unknown_format_raises(self, project: tuple[ProjectStore, Path]):
        store, tmp_path = project
        with pytest.raises(KeyError):
            run_export(
                store,
                "demo",
                ExportRequest(output_dir=str(tmp_path / "x"), format="voc"),
            )

    def test_export_yolo(self, project: tuple[ProjectStore, Path]):
        store, tmp_path = project
        # Project label order defines class ids; "cat" is second on purpose
        store.set_labels("demo", [LabelDef(name="dog"), LabelDef(name="cat")])
        out = tmp_path / "yolo"
        result = run_export(
            store, "demo", ExportRequest(output_dir=str(out), format="yolo", seed=0)
        )
        assert sum(result.counts.values()) == 4

        config = yaml.safe_load((out / "dataset.yaml").read_text())
        assert config["names"] == {0: "dog", 1: "cat"}

        label_files = [f for s in result.counts for f in (out / s / "labels").glob("*.txt")]
        assert len(label_files) == 4
        for txt in label_files:
            (line,) = txt.read_text().splitlines()
            parts = line.split()
            assert parts[0] == "1"  # cat
            vals = [float(v) for v in parts[1:]]
            assert len(vals) == 4
            assert all(0.0 <= v <= 1.0 for v in vals)

    def test_export_yolo_polygon_becomes_bbox(self, project: tuple[ProjectStore, Path]):
        store, tmp_path = project
        store.save_annotation(
            "demo",
            "img_0.png",
            LabelMeDoc(
                shapes=[
                    Shape(
                        label="cat",
                        points=[[0, 0], [30, 0], [15, 20]],
                        shape_type="polygon",
                    )
                ],
                imageHeight=40,
                imageWidth=60,
            ),
        )
        out = tmp_path / "yolo"
        run_export(
            store,
            "demo",
            ExportRequest(
                output_dir=str(out), format="yolo",
                train_ratio=1.0, val_ratio=0.0, test_ratio=0.0, seed=0,
            ),
        )
        line = (out / "train" / "labels" / "img_0.txt").read_text().strip()
        _, xc, yc, w, h = (float(v) for v in line.split())
        # bbox of the polygon: (0,0)-(30,20) in a 60x40 image
        assert (xc, yc, w, h) == (15 / 60, 10 / 40, 30 / 60, 20 / 40)

    def test_export_coco(self, project: tuple[ProjectStore, Path]):
        store, tmp_path = project
        store.set_labels("demo", [LabelDef(name="cat")])
        out = tmp_path / "coco"
        result = run_export(
            store,
            "demo",
            ExportRequest(
                output_dir=str(out), format="coco",
                train_ratio=0.5, val_ratio=0.5, test_ratio=0.0, seed=0,
            ),
        )
        assert result.counts == {"train": 2, "val": 2}
        # val split lands in RF-DETR's expected "valid" directory
        assert not (out / "val").exists()
        for split_dir, count in (("train", 2), ("valid", 2)):
            coco = json.loads((out / split_dir / "_annotations.coco.json").read_text())
            assert len(coco["images"]) == count
            assert len(coco["annotations"]) == count
            assert coco["categories"] == [{"id": 1, "name": "cat"}]
            img = coco["images"][0]
            assert (img["width"], img["height"]) == (60, 40)
            ann = coco["annotations"][0]
            assert ann["bbox"] == [0, 0, 10, 10]
            assert ann["area"] == 100
            assert ann["category_id"] == 1
            # images copied next to the JSON
            assert len(list((out / split_dir).glob("*.png"))) == count

    def test_export_coco_polygon_segmentation(self, project: tuple[ProjectStore, Path]):
        store, tmp_path = project
        pts = [[0, 0], [30, 0], [15, 20]]
        store.save_annotation(
            "demo",
            "img_0.png",
            LabelMeDoc(
                shapes=[Shape(label="cat", points=pts, shape_type="polygon")],
                imageHeight=40,
                imageWidth=60,
            ),
        )
        out = tmp_path / "coco"
        run_export(
            store,
            "demo",
            ExportRequest(
                output_dir=str(out), format="coco",
                train_ratio=1.0, val_ratio=0.0, test_ratio=0.0, seed=0,
            ),
        )
        coco = json.loads((out / "train" / "_annotations.coco.json").read_text())
        seg = next(
            a["segmentation"] for a in coco["annotations"] if a["segmentation"]
        )
        assert seg == [[0, 0, 30, 0, 15, 20]]

    def test_output_inside_images_dir_raises(self, project: tuple[ProjectStore, Path]):
        store, tmp_path = project
        inside = tmp_path / "images" / "export"
        with pytest.raises(ValueError, match="outside"):
            run_export(store, "demo", ExportRequest(output_dir=str(inside)))

    def test_no_annotations_raises(self, tmp_path: Path):
        images_dir = tmp_path / "imgs"
        images_dir.mkdir()
        cv2.imwrite(
            str(images_dir / "a.png"), np.zeros((10, 10, 3), dtype=np.uint8)
        )
        store = ProjectStore(tmp_path / "annotate")
        store.create_project("empty", images_dir)
        with pytest.raises(ValueError, match="No annotated"):
            run_export(store, "empty", ExportRequest(output_dir=str(tmp_path / "o")))
