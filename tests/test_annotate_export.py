"""Tests for dataset splitting and LabelMe export."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from aiops.annotate.export import run_export, split_files
from aiops.annotate.models import ExportRequest, LabelMeDoc, Shape
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
