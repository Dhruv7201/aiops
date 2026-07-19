"""Dataset export: train/val/test splitting + pluggable format exporters.

Formats: labelme (copy-through), yolo (Ultralytics txt + dataset.yaml),
coco (RF-DETR-compatible Roboflow layout). Exporters register into
EXPORTERS with the (images_dir, annotations_dir, output_dir, splits,
class_names) signature.
"""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from PIL import Image

from aiops.annotate.models import ExportRequest, ExportResult
from aiops.annotate.storage import ProjectStore
from aiops.core.log import get_logger
from aiops.core.plugin import PluginRegistry

logger = get_logger(__name__)

EXPORTERS = PluginRegistry("exporter")

# Shape types that convert to a detection box; others are skipped on export
_BOXABLE_TYPES = {"rectangle", "polygon"}


def split_files(
    filenames: list[str],
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    seed: int | None = None,
) -> dict[str, list[str]]:
    """Shuffle and split filenames into train/val(/test) lists.

    Mirrors the index math of aiops.vision.dataset.split_dataset (which is
    YOLO-.txt specific) but is pure — no file copying. test_ratio=0 yields
    a two-way train/val split.
    """
    files = sorted(filenames)
    random.Random(seed).shuffle(files)

    n = len(files)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    splits = {
        "train": files[:n_train],
        "val": files[n_train : n_train + n_val],
    }
    if test_ratio > 0:
        splits["test"] = files[n_train + n_val :]
    else:
        # No test split: remainder goes to val
        splits["val"] = files[n_train:]
    return splits


def _load_doc(annotations_dir: Path, filename: str) -> dict:
    return json.loads((annotations_dir / f"{Path(filename).stem}.json").read_text())


def _doc_dims(doc: dict, images_dir: Path, filename: str) -> tuple[int, int]:
    """(width, height) from the doc, falling back to reading the image."""
    w, h = doc.get("imageWidth", 0), doc.get("imageHeight", 0)
    if w and h:
        return w, h
    with Image.open(images_dir / filename) as img:
        return img.size


def _shape_bbox(points: list[list[float]]) -> tuple[float, float, float, float]:
    """Axis-aligned (x1, y1, x2, y2) around any point list."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def export_labelme(
    images_dir: Path,
    annotations_dir: Path,
    output_dir: Path,
    splits: dict[str, list[str]],
    class_names: list[str],
) -> dict[str, int]:
    """Copy images + LabelMe JSONs into <split>/images and <split>/labels."""
    counts: dict[str, int] = {}
    for split, filenames in splits.items():
        if not filenames:
            continue
        img_out = output_dir / split / "images"
        lbl_out = output_dir / split / "labels"
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            shutil.copy2(images_dir / filename, img_out / filename)
            ann_path = annotations_dir / f"{Path(filename).stem}.json"
            doc = json.loads(ann_path.read_text())
            doc["imagePath"] = f"../images/{filename}"
            (lbl_out / ann_path.name).write_text(
                json.dumps(doc, indent=2, ensure_ascii=False)
            )
        counts[split] = len(filenames)
    return counts


def export_yolo(
    images_dir: Path,
    annotations_dir: Path,
    output_dir: Path,
    splits: dict[str, list[str]],
    class_names: list[str],
) -> dict[str, int]:
    """Export to Ultralytics YOLO detection format.

    <split>/images/, <split>/labels/<stem>.txt with normalized
    `cls xc yc w h` lines, plus dataset.yaml at the root. Polygons are
    reduced to their bounding box (segmentation export may come later);
    other shape types are skipped.
    """
    from aiops.vision.dataset import create_yolo_yaml

    class_ids = {name: i for i, name in enumerate(class_names)}
    counts: dict[str, int] = {}
    for split, filenames in splits.items():
        if not filenames:
            continue
        img_out = output_dir / split / "images"
        lbl_out = output_dir / split / "labels"
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            shutil.copy2(images_dir / filename, img_out / filename)
            doc = _load_doc(annotations_dir, filename)
            w, h = _doc_dims(doc, images_dir, filename)
            lines = []
            for shape in doc.get("shapes", []):
                if shape.get("shape_type") not in _BOXABLE_TYPES:
                    continue
                x1, y1, x2, y2 = _shape_bbox(shape["points"])
                xc, yc = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
                bw, bh = (x2 - x1) / w, (y2 - y1) / h
                cls = class_ids[shape["label"]]
                lines.append(f"{cls} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
            (lbl_out / f"{Path(filename).stem}.txt").write_text("\n".join(lines))
        counts[split] = len(filenames)

    create_yolo_yaml(
        dataset_dir=output_dir,
        classes=class_names,
        output_path=output_dir / "dataset.yaml",
        test_dir="test/images" if splits.get("test") else None,
    )
    return counts


# RF-DETR's loader expects Roboflow's train/valid/test directory names
_COCO_SPLIT_DIRS = {"val": "valid"}


def export_coco(
    images_dir: Path,
    annotations_dir: Path,
    output_dir: Path,
    splits: dict[str, list[str]],
    class_names: list[str],
) -> dict[str, int]:
    """Export to COCO JSON in the Roboflow layout RF-DETR consumes.

    <split>/ holds the images plus _annotations.coco.json; the val split
    is written as valid/. Category ids are 1-based. Polygons keep their
    points as segmentation; other non-boxable shape types are skipped.
    """
    categories = [{"id": i + 1, "name": n} for i, n in enumerate(class_names)]
    category_ids = {n: i + 1 for i, n in enumerate(class_names)}

    counts: dict[str, int] = {}
    for split, filenames in splits.items():
        if not filenames:
            continue
        split_out = output_dir / _COCO_SPLIT_DIRS.get(split, split)
        split_out.mkdir(parents=True, exist_ok=True)

        images, annotations = [], []
        ann_id = 1
        for image_id, filename in enumerate(filenames, start=1):
            shutil.copy2(images_dir / filename, split_out / filename)
            doc = _load_doc(annotations_dir, filename)
            w, h = _doc_dims(doc, images_dir, filename)
            images.append(
                {"id": image_id, "file_name": filename, "width": w, "height": h}
            )
            for shape in doc.get("shapes", []):
                if shape.get("shape_type") not in _BOXABLE_TYPES:
                    continue
                x1, y1, x2, y2 = _shape_bbox(shape["points"])
                ann = {
                    "id": ann_id,
                    "image_id": image_id,
                    "category_id": category_ids[shape["label"]],
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "area": (x2 - x1) * (y2 - y1),
                    "iscrowd": 0,
                    "segmentation": [],
                }
                if shape["shape_type"] == "polygon":
                    ann["segmentation"] = [
                        [coord for pt in shape["points"] for coord in pt]
                    ]
                annotations.append(ann)
                ann_id += 1

        (split_out / "_annotations.coco.json").write_text(
            json.dumps(
                {"images": images, "annotations": annotations, "categories": categories},
                indent=2,
                ensure_ascii=False,
            )
        )
        counts[split] = len(filenames)
    return counts


EXPORTERS.register("labelme", export_labelme)
EXPORTERS.register("yolo", export_yolo)
EXPORTERS.register("coco", export_coco)


def _collect_class_names(
    store: ProjectStore, project_name: str, annotated: list[str]
) -> list[str]:
    """Project labels in defined order, plus any extras found in the docs."""
    class_names = [label.name for label in store.load_project(project_name).labels]
    known = set(class_names)
    extras = set()
    for filename in annotated:
        for shape in store.load_annotation(project_name, filename).shapes:
            if shape.label not in known:
                extras.add(shape.label)
    return class_names + sorted(extras)


def run_export(store: ProjectStore, project_name: str, req: ExportRequest) -> ExportResult:
    """Export all annotated images of a project into split directories."""
    exporter = EXPORTERS.get(req.format)

    annotated = [i.filename for i in store.list_images(project_name) if i.annotated]
    if not annotated:
        raise ValueError("No annotated images to export")

    splits = split_files(
        annotated,
        train_ratio=req.train_ratio,
        val_ratio=req.val_ratio,
        test_ratio=req.test_ratio,
        seed=req.seed,
    )
    output_dir = Path(req.output_dir).expanduser().resolve()
    images_dir = store.images_dir(project_name).resolve()
    if output_dir == images_dir or images_dir in output_dir.parents:
        raise ValueError(
            f"output_dir must be outside the project images directory ({images_dir})"
        )
    class_names = _collect_class_names(store, project_name, annotated)
    counts = exporter(
        images_dir, images_dir / ".annotations", output_dir, splits, class_names
    )
    logger.info(f"Exported '{project_name}' to {output_dir}: {counts}")
    return ExportResult(output_dir=str(output_dir), counts=counts)
