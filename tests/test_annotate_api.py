"""API tests for the annotation server (requires fastapi)."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from aiops.annotate.server import create_app  # noqa: E402


@pytest.fixture
def images_dir(tmp_path: Path) -> Path:
    d = tmp_path / "images"
    d.mkdir()
    img = np.zeros((50, 70, 3), dtype=np.uint8)
    for i in range(4):
        cv2.imwrite(str(d / f"img_{i}.png"), img)
    return d


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(annotate_dir=tmp_path / "annotate"))


class TestFullFlow:
    def test_end_to_end(self, client: TestClient, images_dir: Path, tmp_path: Path):
        # Users
        assert client.post("/api/users", json={"name": "alice"}).status_code == 201
        client.post("/api/users", json={"name": "bob"})
        assert client.get("/api/users").json() == ["alice", "bob"]

        # Project
        r = client.post(
            "/api/projects", json={"name": "demo", "images_dir": str(images_dir)}
        )
        assert r.status_code == 201

        r = client.get("/api/projects")
        assert r.json()[0]["num_images"] == 4

        # Labels
        r = client.put(
            "/api/projects/demo/labels",
            json={"labels": [{"name": "cat", "color": "#ff0000"}]},
        )
        assert r.json()["labels"][0]["name"] == "cat"

        # Assign
        r = client.post(
            "/api/projects/demo/assign", json={"users": ["alice", "bob"]}
        )
        assignments = r.json()["assignments"]
        assert len(assignments) == 4
        assert set(assignments.values()) == {"alice", "bob"}

        # Manual reassign
        r = client.put(
            "/api/projects/demo/assign",
            json={"filename": "img_0.png", "user": "bob"},
        )
        assert r.json()["assignments"]["img_0.png"] == "bob"

        # Skeleton annotation
        r = client.get("/api/projects/demo/annotations/img_0.png")
        doc = r.json()
        assert doc["shapes"] == []
        assert doc["imageWidth"] == 70

        # Save annotation
        doc["shapes"] = [
            {
                "label": "cat",
                "points": [[5, 5], [30, 30]],
                "shape_type": "rectangle",
                "group_id": None,
                "description": "",
                "flags": {},
            }
        ]
        r = client.put("/api/projects/demo/annotations/img_0.png", json=doc)
        assert r.json() == {"saved": True}

        # Status reflected in image list
        images = client.get("/api/projects/demo/images").json()
        img0 = next(i for i in images if i["filename"] == "img_0.png")
        assert img0["annotated"] and img0["num_shapes"] == 1

        # Written file is valid LabelMe
        saved = json.loads(
            (images_dir / ".annotations" / "img_0.json").read_text()
        )
        assert saved["imagePath"] == "../img_0.png"
        assert saved["imageData"] is None

        # Image bytes served
        assert client.get("/api/projects/demo/images/img_0.png").status_code == 200

        # Export (only 1 annotated image → all-train split)
        r = client.post(
            "/api/projects/demo/export",
            json={
                "output_dir": str(tmp_path / "export"),
                "train_ratio": 1.0,
                "val_ratio": 0.0,
                "test_ratio": 0.0,
            },
        )
        assert r.status_code == 200
        assert r.json()["counts"] == {"train": 1}


class TestErrors:
    def test_unknown_project_404(self, client: TestClient):
        assert client.get("/api/projects/nope").status_code == 404

    def test_missing_images_dir_404(self, client: TestClient, tmp_path: Path):
        r = client.post(
            "/api/projects",
            json={"name": "x", "images_dir": str(tmp_path / "missing")},
        )
        assert r.status_code == 404

    def test_duplicate_project_409(self, client: TestClient, images_dir: Path):
        client.post("/api/projects", json={"name": "d", "images_dir": str(images_dir)})
        r = client.post(
            "/api/projects", json={"name": "d", "images_dir": str(images_dir)}
        )
        assert r.status_code == 409

    def test_path_traversal_rejected(self, client: TestClient, images_dir: Path, tmp_path: Path):
        (tmp_path / "secret.png").write_bytes(b"top secret")
        client.post("/api/projects", json={"name": "d", "images_dir": str(images_dir)})
        r = client.get("/api/projects/d/images/..%2Fsecret.png")
        assert r.status_code == 404

    def test_bad_ratios_422(self, client: TestClient, images_dir: Path, tmp_path: Path):
        client.post("/api/projects", json={"name": "d", "images_dir": str(images_dir)})
        r = client.post(
            "/api/projects/d/export",
            json={"output_dir": str(tmp_path / "o"), "train_ratio": 0.9,
                  "val_ratio": 0.9, "test_ratio": 0.0},
        )
        assert r.status_code == 422

    def test_export_no_annotations_400(self, client: TestClient, images_dir: Path, tmp_path: Path):
        client.post("/api/projects", json={"name": "d", "images_dir": str(images_dir)})
        r = client.post(
            "/api/projects/d/export",
            json={"output_dir": str(tmp_path / "o"), "train_ratio": 1.0,
                  "val_ratio": 0.0, "test_ratio": 0.0},
        )
        assert r.status_code == 400
