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

    def test_atomic_write_leaves_no_tmp(self, store: ProjectStore, images_dir: Path):
        store.create_project("demo", images_dir)
        store.save_annotation(
            "demo", "img_0.png", LabelMeDoc(imageHeight=80, imageWidth=120)
        )
        assert not list((images_dir / ".annotations").glob("*.tmp"))

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
