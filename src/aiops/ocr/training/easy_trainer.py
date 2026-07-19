"""EasyOCR training pipeline.

EasyOCR custom training uses the deep-text-recognition-benchmark (DTRB) repo.
This trainer automates dataset preparation and launches DTRB training.

Setup:
    git clone https://github.com/JaidedAI/EasyOCR.git
    cd EasyOCR/trainer
    pip install -r requirements.txt
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from aiops.core.log import get_logger

logger = get_logger(__name__)


class EasyOCRTrainer:
    """Training pipeline for EasyOCR custom recognition models.

    Uses the EasyOCR trainer (DTRB-based) from the official repo.

    Expected dataset structure (after prepare_dataset):
        dataset/
        ├── train/
        │   ├── img1.jpg
        │   ├── img2.jpg
        │   └── ...
        ├── val/
        │   ├── img1.jpg
        │   └── ...
        ├── train_gt.txt      # img_path\\tlabel
        └── val_gt.txt

    Usage:
        trainer = EasyOCRTrainer(
            dataset_dir="dataset/",
            trainer_dir="EasyOCR/trainer/",
        )
        trainer.prepare_dataset("raw_images/", "annotations.json")
        trainer.train(epochs=100, batch_size=64)
    """

    def __init__(
        self,
        dataset_dir: str | Path,
        output_dir: str | Path = "output",
        trainer_dir: str | Path | None = None,
    ) -> None:
        self.dataset_dir = Path(dataset_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Path to cloned EasyOCR/trainer directory
        self.trainer_dir = Path(trainer_dir) if trainer_dir else None

    def prepare_dataset(
        self,
        images_dir: str | Path,
        annotations_file: str | Path,
        output_dir: str | Path | None = None,
        train_ratio: float = 0.8,
    ) -> Path:
        """Convert raw annotations to EasyOCR/DTRB training format.

        DTRB expects:
            - Images in a directory
            - Ground truth file: image_path\\tlabel (one per line)

        Args:
            images_dir: directory with source images.
            annotations_file: JSON mapping {"filename": "text"}.
            output_dir: destination directory.
            train_ratio: train/val split ratio.
        """
        images = Path(images_dir)
        out = Path(output_dir or self.dataset_dir)

        with open(annotations_file) as f:
            annotations: dict[str, str] = json.load(f)

        items = list(annotations.items())
        split_idx = int(len(items) * train_ratio)
        splits = {"train": items[:split_idx], "val": items[split_idx:]}

        for split_name, split_items in splits.items():
            split_dir = out / split_name
            split_dir.mkdir(parents=True, exist_ok=True)
            gt_lines = []

            for filename, text in split_items:
                src = images / filename
                if src.exists():
                    shutil.copy2(src, split_dir / filename)
                    gt_lines.append(f"{split_name}/{filename}\t{text}")

            gt_file = out / f"{split_name}_gt.txt"
            gt_file.write_text("\n".join(gt_lines) + "\n")
            logger.info(f"Prepared {split_name}: {len(gt_lines)} samples -> {gt_file}")

        return out

    def create_lmdb(self, split: str = "train") -> Path:
        """Convert dataset split to LMDB format (required by DTRB).

        Args:
            split: 'train' or 'val'.

        Returns:
            Path to LMDB directory.
        """
        if not self.trainer_dir:
            raise RuntimeError(
                "trainer_dir not set. Clone the EasyOCR repo and pass trainer_dir='EasyOCR/trainer/'"
            )

        create_lmdb_script = self.trainer_dir / "create_lmdb_dataset.py"
        if not create_lmdb_script.exists():
            raise FileNotFoundError(f"LMDB creation script not found: {create_lmdb_script}")

        gt_file = self.dataset_dir / f"{split}_gt.txt"
        lmdb_dir = self.output_dir / "lmdb" / split

        cmd = [
            "python", str(create_lmdb_script),
            "--inputPath", str(self.dataset_dir),
            "--gtFile", str(gt_file),
            "--outputPath", str(lmdb_dir),
        ]

        logger.info(f"Creating LMDB for {split}: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return lmdb_dir

    def train(
        self,
        epochs: int = 100,
        batch_size: int = 64,
        learning_rate: float = 1.0,
        imgH: int = 64,
        imgW: int = 600,
        num_workers: int = 4,
        pretrained: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Launch EasyOCR/DTRB training.

        Args:
            epochs: number of training epochs.
            batch_size: training batch size.
            learning_rate: Adadelta learning rate.
            imgH: input image height.
            imgW: input image width.
            num_workers: dataloader workers.
            pretrained: path to pretrained model for fine-tuning.
        """
        if not self.trainer_dir:
            raise RuntimeError(
                "trainer_dir not set. Clone the EasyOCR repo and pass "
                "trainer_dir='EasyOCR/trainer/'"
            )

        train_script = self.trainer_dir / "train.py"
        if not train_script.exists():
            raise FileNotFoundError(f"Training script not found: {train_script}")

        # Create LMDB datasets if they don't exist
        train_lmdb = self.output_dir / "lmdb" / "train"
        val_lmdb = self.output_dir / "lmdb" / "val"
        if not train_lmdb.exists():
            self.create_lmdb("train")
        if not val_lmdb.exists():
            self.create_lmdb("val")

        cmd = [
            "python", str(train_script),
            "--train_data", str(train_lmdb),
            "--valid_data", str(val_lmdb),
            "--exp_name", self.output_dir.name,
            "--num_iter", str(epochs * 1000),
            "--batch_size", str(batch_size),
            "--lr", str(learning_rate),
            "--imgH", str(imgH),
            "--imgW", str(imgW),
            "--workers", str(num_workers),
            "--Transformation", "None",
            "--FeatureExtraction", "ResNet",
            "--SequenceModeling", "BiLSTM",
            "--Prediction", "CTC",
        ]

        # DTRB's --saved_model is the *pretrained* checkpoint to fine-tune from
        if pretrained:
            cmd.extend(["--saved_model", str(pretrained)])

        for key, val in kwargs.items():
            cmd.extend([f"--{key}", str(val)])

        logger.info(f"Launching EasyOCR training: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, cwd=str(self.trainer_dir))
