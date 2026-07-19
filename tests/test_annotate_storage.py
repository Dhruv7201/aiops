"""Tests for annotation project storage."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from aiops.annotate.models import LabelDef, LabelMeDoc, Shape
from aiops.annotate.storage import ProjectStore


@pytest.fixture
def images_dir(tmp_path: Path) -> Path:
    """Directory with three small PNGs of known size."""
    d = tmp_path / "images"
    d.mkdir()
    img = np.zeros((80, 120, 3), dtype=np.uint8)  # 120x80 (WxH)
    for i in range(3):
        cv2.imwrite(str(d / f"img_{i}.png"), img)
    (d / "notes.txt").write_text("not an image")
    return d


@pytest.fixture
def store(tmp_path: Path) -> ProjectStore:
    return ProjectStore(tmp_path / "annotate")


class TestUsers:
    def test_add_and_list(self, store: ProjectStore):
        assert store.list_users() == []
        store.add_user("alice")
        store.add_user("bob")
        store.add_user("alice")  # duplicate ignored
        assert store.list_users() == ["alice", "bob"]


class TestProjects:
    def test_create_project(self, store: ProjectStore, images_dir: Path):
        meta = store.create_project("demo", images_dir)
        assert meta.name == "demo"
        assert (images_dir / ".annotations" / "project.json").exists()

    def test_create_missing_dir_raises(self, store: ProjectStore, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            store.create_project("demo", tmp_path / "nope")

    def test_duplicate_name_raises(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        with pytest.raises(FileExistsError):
            store.create_project("demo", images_dir)

    def test_list_projects_counts(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        doc = LabelMeDoc(
            shapes=[Shape(label="cat", points=[[0, 0], [10, 10]])],
            imageHeight=80,
            imageWidth=120,
        )
        store.save_annotation("demo", "img_0.png", doc)

        (summary,) = store.list_projects()
        assert summary.num_images == 3
        assert summary.num_annotated == 1

    def test_set_labels_roundtrip(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        store.set_labels("demo", [LabelDef(name="cat", color="#ff0000")])
        meta = store.load_project("demo")
        assert meta.labels[0].name == "cat"

    def test_reopen_existing_annotations_dir(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        store.set_labels("demo", [LabelDef(name="cat")])
        # A second registry (fresh machine) opening the same dir keeps labels
        store2 = ProjectStore(store.annotate_dir.parent / "other")
        meta = store2.create_project("demo2", images_dir)
        assert meta.labels[0].name == "cat"

    def test_delete_project_keeps_annotations(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        store.delete_project("demo")
        assert store.list_projects() == []
        assert (images_dir / ".annotations" / "project.json").exists()
        with pytest.raises(KeyError):
            store.delete_project("demo")

    def test_rename_project(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        store.set_labels("demo", [LabelDef(name="cat")])
        meta = store.rename_project("demo", "renamed")
        assert meta.name == "renamed"
        assert [p.name for p in store.list_projects()] == ["renamed"]
        # labels survive the rename and load under the new name
        assert store.load_project("renamed").labels[0].name == "cat"

    def test_rename_to_existing_raises(self, store: ProjectStore, images_dir: Path, tmp_path: Path):
        other = tmp_path / "other_images"
        other.mkdir()
        cv2.imwrite(str(other / "x.png"), np.zeros((10, 10, 3), dtype=np.uint8))
        store.create_project("a", images_dir)
        store.create_project("b", other)
        with pytest.raises(FileExistsError):
            store.rename_project("a", "b")


class TestImages:
    def test_list_images_skips_non_images(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        images = store.list_images("demo")
        assert [i.filename for i in images] == ["img_0.png", "img_1.png", "img_2.png"]
        assert images[0].width == 120
        assert images[0].height == 80
        assert not images[0].annotated

    def test_image_path_rejects_traversal(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        with pytest.raises(FileNotFoundError):
            store.image_path("demo", "../secret.png")

    def test_corrupt_image_skipped(self, store: ProjectStore, images_dir: Path):
        (images_dir / "broken.png").write_bytes(b"not a real png")
        store.create_project("demo", images_dir)
        images = store.list_images("demo")
        assert "broken.png" not in [i.filename for i in images]
        assert len(images) == 3
        # project listing also survives the corrupt file
        (summary,) = store.list_projects()
        assert summary.num_images == 3

    def test_stem_collision_rejected(self, store: ProjectStore, images_dir: Path):
        import shutil

        shutil.copy2(images_dir / "img_0.png", images_dir / "img_0.jpg")
        with pytest.raises(ValueError, match="share the same"):
            store.create_project("demo", images_dir)

    def test_dims_cache_written_and_invalidated(self, store: ProjectStore, images_dir: Path):
        import json
        import os

        store.create_project("demo", images_dir)
        store.list_images("demo")
        cache_path = images_dir / ".annotations" / "dims.json"
        cache = json.loads(cache_path.read_text())
        assert cache["img_0.png"][:2] == [120, 80]

        # Replace an image with different dims and bump mtime → re-scanned
        cv2.imwrite(str(images_dir / "img_0.png"), np.zeros((50, 70, 3), dtype=np.uint8))
        stat = (images_dir / "img_0.png").stat()
        os.utime(images_dir / "img_0.png", ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
        info = next(i for i in store.list_images("demo") if i.filename == "img_0.png")
        assert (info.width, info.height) == (70, 50)


class TestAnnotations:
    def test_skeleton_doc(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        doc = store.load_annotation("demo", "img_1.png")
        assert doc.shapes == []
        assert doc.imagePath == "../img_1.png"
        assert (doc.imageWidth, doc.imageHeight) == (120, 80)

    def test_save_load_roundtrip(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        doc = LabelMeDoc(
            shapes=[
                Shape(label="cat", points=[[1, 2], [30, 40]]),
                Shape(
                    label="dog",
                    points=[[0, 0], [10, 0], [10, 10]],
                    shape_type="polygon",
                ),
            ],
            imageHeight=80,
            imageWidth=120,
        )
        store.save_annotation("demo", "img_0.png", doc)

        loaded = store.load_annotation("demo", "img_0.png")
        assert len(loaded.shapes) == 2
        assert loaded.shapes[1].shape_type == "polygon"
        assert loaded.imagePath == "../img_0.png"
        assert loaded.imageData is None

    def test_labelme_image_data_accepted_and_stripped(
        self, store: ProjectStore, images_dir: Path
    ):
        store.create_project("demo", images_dir)
        # Real LabelMe files embed the image as base64 in imageData
        raw = LabelMeDoc(
            shapes=[Shape(label="cat", points=[[0, 0], [5, 5]])],
            imageData="aGVsbG8=",
            imageHeight=80,
            imageWidth=120,
        )
        store.save_annotation("demo", "img_0.png", raw)
        loaded = store.load_annotation("demo", "img_0.png")
        assert loaded.imageData is None
        assert len(loaded.shapes) == 1

    def test_load_external_labelme_file(self, store: ProjectStore, images_dir: Path):
        # A doc written by LabelMe itself (with imageData) must load cleanly
        store.create_project("demo", images_dir)
        import json

        ann = images_dir / ".annotations" / "img_1.json"
        ann.write_text(
            json.dumps(
                {
                    "version": "5.4.1",
                    "flags": {},
                    "shapes": [],
                    "imagePath": "../img_1.png",
                    "imageData": "aGVsbG8=",
                    "imageHeight": 80,
                    "imageWidth": 120,
                }
            )
        )
        doc = store.load_annotation("demo", "img_1.png")
        assert doc.imageData == "aGVsbG8="

    def test_atomic_write_leaves_no_tmp(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        store.save_annotation(
            "demo", "img_0.png", LabelMeDoc(imageHeight=80, imageWidth=120)
        )
        assert not list((images_dir / ".annotations").glob("*.tmp"))

    def test_other_labelme_shape_types_load(self, store: ProjectStore, images_dir: Path):
        # Docs written by LabelMe can contain circle/line/point/linestrip
        store.create_project("demo", images_dir)
        doc = LabelMeDoc(
            shapes=[
                Shape(label="c", points=[[10, 10], [20, 10]], shape_type="circle"),
                Shape(label="l", points=[[0, 0], [5, 5]], shape_type="line"),
                Shape(label="p", points=[[3, 3]], shape_type="point"),
                Shape(
                    label="s",
                    points=[[0, 0], [5, 5], [10, 0]],
                    shape_type="linestrip",
                ),
            ],
            imageHeight=80,
            imageWidth=120,
        )
        store.save_annotation("demo", "img_0.png", doc)
        loaded = store.load_annotation("demo", "img_0.png")
        assert [s.shape_type for s in loaded.shapes] == [
            "circle", "line", "point", "linestrip",
        ]

    def test_annotated_flag_flips(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        assert not store.list_images("demo")[0].annotated
        store.save_annotation(
            "demo",
            "img_0.png",
            LabelMeDoc(
                shapes=[Shape(label="x", points=[[0, 0], [5, 5]])],
                imageHeight=80,
                imageWidth=120,
            ),
        )
        info = store.list_images("demo")[0]
        assert info.annotated
        assert info.num_shapes == 1
