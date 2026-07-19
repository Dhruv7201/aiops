"""Dataset export: train/val/test splitting + pluggable format exporters.

Only LabelMe format for now; YOLO / RF-DETR exporters register into
EXPORTERS later with the same (images_dir, annotations_dir, output_dir,
splits) signature.
"""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from aiops.annotate.models import ExportRequest, ExportResult
from aiops.annotate.storage import ProjectStore
from aiops.core.log import get_logger
from aiops.core.plugin import PluginRegistry

logger = get_logger(__name__)

EXPORTERS = PluginRegistry("exporter")


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


def export_labelme(
    images_dir: Path,
    annotations_dir: Path,
    output_dir: Path,
    splits: dict[str, list[str]],
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


EXPORTERS.register("labelme", export_labelme)


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
    images_dir = store.images_dir(project_name)
    counts = exporter(images_dir, images_dir / ".annotations", output_dir, splits)
    logger.info(f"Exported '{project_name}' to {output_dir}: {counts}")
    return ExportResult(output_dir=str(output_dir), counts=counts)
