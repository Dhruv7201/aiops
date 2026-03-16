"""PaddleOCR training pipeline.

Supports two modes:
1. Standalone PaddleOCR repo (tools/train.py) — works with 2.x
2. PaddleX CLI — works with 3.x

Requires cloning PaddleOCR repo for standalone mode:
    git clone https://github.com/PaddlePaddle/PaddleOCR.git
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from aiops.core.log import get_logger

logger = get_logger(__name__)

# Default base configs shipped with PaddleOCR repo
_BASE_CONFIGS = {
    "rec": "configs/rec/PP-OCRv4/en_PP-OCRv4_rec.yml",
    "det": "configs/det/ch_PP-OCRv4/ch_PP-OCRv4_det_student.yml",
}


class PaddleTrainer:
    """Training pipeline for PaddleOCR (detection + recognition).

    Expected dataset structure (recognition):
        dataset/
        ├── train/
        │   ├── images/
        │   └── labels.txt    # image_path\\ttext
        ├── val/
        │   ├── images/
        │   └── labels.txt
        └── dict.txt          # character dictionary (one char per line)

    Expected dataset structure (detection):
        dataset/
        ├── train/
        │   ├── images/
        │   └── labels.txt    # image_path\\t[{"transcription":"...", "points":[[x,y],...]}]
        └── val/
            ├── images/
            └── labels.txt

    Usage:
        trainer = PaddleTrainer(
            dataset_dir="dataset/",
            paddleocr_dir="PaddleOCR/",  # cloned repo
        )
        trainer.prepare_dataset("raw_images/", "annotations.json")
        trainer.train(task="rec", epochs=200, pretrained="en_PP-OCRv4_rec_train/best_accuracy")
    """

    def __init__(
        self,
        dataset_dir: str | Path,
        output_dir: str | Path = "output",
        paddleocr_dir: str | Path | None = None,
    ) -> None:
        self.dataset_dir = Path(dataset_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.paddleocr_dir = Path(paddleocr_dir) if paddleocr_dir else None

    def prepare_dataset(
        self,
        images_dir: str | Path,
        annotations_file: str | Path,
        output_dir: str | Path | None = None,
        train_ratio: float = 0.8,
    ) -> Path:
        """Convert raw data into PaddleOCR recognition training format.

        Args:
            images_dir: directory containing cropped text images.
            annotations_file: JSON file — {"filename": "text"} mappings.
            output_dir: where to write the formatted dataset.
            train_ratio: train/val split ratio.

        Returns:
            Path to the prepared dataset directory.
        """
        images = Path(images_dir)
        out = Path(output_dir or self.dataset_dir)

        with open(annotations_file) as f:
            annotations: dict[str, str] = json.load(f)

        items = list(annotations.items())
        split_idx = int(len(items) * train_ratio)
        splits = {"train": items[:split_idx], "val": items[split_idx:]}

        # Build character dictionary from all text
        chars = set()
        for _, text in items:
            chars.update(text)
        dict_path = out / "dict.txt"
        dict_path.write_text("\n".join(sorted(chars)) + "\n")
        logger.info(f"Generated dict with {len(chars)} characters -> {dict_path}")

        for split_name, split_items in splits.items():
            split_dir = out / split_name / "images"
            split_dir.mkdir(parents=True, exist_ok=True)
            labels = []

            for filename, text in split_items:
                src = images / filename
                if src.exists():
                    shutil.copy2(src, split_dir / filename)
                    labels.append(f"{split_name}/images/{filename}\t{text}")

            label_file = out / split_name / "labels.txt"
            label_file.write_text("\n".join(labels) + "\n")
            logger.info(f"Prepared {split_name}: {len(labels)} samples -> {label_file}")

        return out

    def generate_config(
        self,
        task: str = "rec",
        base_config: str | Path | None = None,
        pretrained: str | None = None,
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        num_workers: int = 4,
        **overrides: Any,
    ) -> Path:
        """Generate a PaddleOCR YAML training config.

        Args:
            task: 'det' for detection, 'rec' for recognition.
            base_config: path to base YAML config from PaddleOCR repo.
                         If None, uses default config for the task.
            pretrained: path to pretrained model for fine-tuning.
            epochs: number of training epochs.
            batch_size: training batch size.
            learning_rate: initial learning rate.
            num_workers: dataloader workers.

        Returns:
            Path to the generated YAML config file.
        """
        # Load base config if provided, otherwise build from scratch
        if base_config and Path(base_config).exists():
            with open(base_config) as f:
                config = yaml.safe_load(f)
        elif self.paddleocr_dir:
            default_base = self.paddleocr_dir / _BASE_CONFIGS.get(task, _BASE_CONFIGS["rec"])
            if default_base.exists():
                with open(default_base) as f:
                    config = yaml.safe_load(f)
            else:
                config = self._build_config_from_scratch(task)
        else:
            config = self._build_config_from_scratch(task)

        # Override with our dataset/training settings
        config.setdefault("Global", {})
        config["Global"]["epoch_num"] = epochs
        config["Global"]["save_model_dir"] = str(self.output_dir / "models" / task)
        config["Global"]["save_epoch_step"] = max(1, epochs // 10)
        config["Global"]["eval_batch_step"] = [0, 500]
        config["Global"]["print_batch_step"] = 50
        config["Global"]["use_gpu"] = True

        if pretrained:
            config["Global"]["pretrained_model"] = str(pretrained)

        if task == "rec":
            config["Global"]["character_dict_path"] = str(self.dataset_dir / "dict.txt")
            config["Global"]["max_text_length"] = overrides.get("max_text_length", 25)

        # Train dataset
        config.setdefault("Train", {}).setdefault("dataset", {})
        config["Train"]["dataset"]["name"] = "SimpleDataSet"
        config["Train"]["dataset"]["data_dir"] = str(self.dataset_dir)
        config["Train"]["dataset"]["label_file_list"] = [
            str(self.dataset_dir / "train" / "labels.txt")
        ]
        config["Train"].setdefault("loader", {})
        config["Train"]["loader"]["batch_size_per_card"] = batch_size
        config["Train"]["loader"]["num_workers"] = num_workers
        config["Train"]["loader"]["shuffle"] = True

        # Eval dataset
        config.setdefault("Eval", {}).setdefault("dataset", {})
        config["Eval"]["dataset"]["name"] = "SimpleDataSet"
        config["Eval"]["dataset"]["data_dir"] = str(self.dataset_dir)
        config["Eval"]["dataset"]["label_file_list"] = [
            str(self.dataset_dir / "val" / "labels.txt")
        ]
        config["Eval"].setdefault("loader", {})
        config["Eval"]["loader"]["batch_size_per_card"] = batch_size
        config["Eval"]["loader"]["num_workers"] = num_workers

        # Optimizer
        config.setdefault("Optimizer", {})
        config["Optimizer"]["name"] = "Adam"
        config["Optimizer"]["lr"] = {
            "name": "Cosine",
            "learning_rate": learning_rate,
            "warmup_epoch": min(5, epochs // 10),
        }

        config_path = self.output_dir / f"{task}_config.yml"
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        logger.info(f"Training config written to {config_path}")
        return config_path

    def train(
        self,
        task: str = "rec",
        config: str | Path | None = None,
        pretrained: str | None = None,
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        **kwargs: Any,
    ) -> None:
        """Launch PaddleOCR training.

        Requires PaddleOCR repo cloned locally (paddleocr_dir).

        Args:
            task: 'det' or 'rec'.
            config: path to existing YAML config. Generated if None.
            pretrained: pretrained model path for fine-tuning.
            epochs: number of epochs.
            batch_size: batch size.
            learning_rate: initial learning rate.
        """
        config_path = config or self.generate_config(
            task=task,
            pretrained=pretrained,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            **kwargs,
        )

        if self.paddleocr_dir and (self.paddleocr_dir / "tools" / "train.py").exists():
            # Standalone mode — use PaddleOCR repo's train.py
            cmd = [
                "python",
                str(self.paddleocr_dir / "tools" / "train.py"),
                "-c", str(config_path),
            ]
        else:
            # Try PaddleX CLI (PaddleOCR 3.x)
            cmd = [
                "python", "-m", "paddlex",
                "--pipeline", "OCR",
                "--config", str(config_path),
                "--mode", "train",
            ]
            logger.warning(
                "paddleocr_dir not set — falling back to PaddleX CLI. "
                "For best results, clone PaddleOCR and pass paddleocr_dir."
            )

        logger.info(f"Launching training: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, cwd=str(self.paddleocr_dir or "."))

    def evaluate(
        self,
        task: str = "rec",
        model_dir: str | Path | None = None,
        config: str | Path | None = None,
    ) -> None:
        """Evaluate a trained model.

        Args:
            task: 'det' or 'rec'.
            model_dir: directory containing the trained model.
            config: path to config YAML used during training.
        """
        model = Path(model_dir or self.output_dir / "models" / task)
        config_path = config or self.output_dir / f"{task}_config.yml"

        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config not found: {config_path}. Run train() first.")

        if self.paddleocr_dir and (self.paddleocr_dir / "tools" / "eval.py").exists():
            cmd = [
                "python",
                str(self.paddleocr_dir / "tools" / "eval.py"),
                "-c", str(config_path),
                "-o", f"Global.checkpoints={model / 'best_accuracy'}",
            ]
        else:
            cmd = [
                "python", "-m", "paddlex",
                "--pipeline", "OCR",
                "--config", str(config_path),
                "--mode", "evaluate",
            ]

        logger.info(f"Launching evaluation: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, cwd=str(self.paddleocr_dir or "."))

    def export(
        self,
        task: str = "rec",
        model_dir: str | Path | None = None,
        config: str | Path | None = None,
    ) -> Path:
        """Export trained model to inference format.

        Returns:
            Path to exported inference model directory.
        """
        model = Path(model_dir or self.output_dir / "models" / task)
        config_path = config or self.output_dir / f"{task}_config.yml"
        export_dir = self.output_dir / "inference" / task

        if not self.paddleocr_dir or not (self.paddleocr_dir / "tools" / "export_model.py").exists():
            raise RuntimeError("Export requires paddleocr_dir pointing to cloned PaddleOCR repo.")

        cmd = [
            "python",
            str(self.paddleocr_dir / "tools" / "export_model.py"),
            "-c", str(config_path),
            "-o", f"Global.pretrained_model={model / 'best_accuracy'}",
            "-o", f"Global.save_inference_dir={export_dir}",
        ]

        logger.info(f"Exporting model: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, cwd=str(self.paddleocr_dir))
        return export_dir

    @staticmethod
    def _build_config_from_scratch(task: str) -> dict:
        """Build a minimal PaddleOCR config when no base config is available."""
        if task == "rec":
            return {
                "Global": {
                    "use_gpu": True,
                    "character_type": "en",
                    "loss_type": "ctc",
                },
                "Architecture": {
                    "model_type": "rec",
                    "algorithm": "SVTR_LCNet",
                    "Transform": None,
                    "Backbone": {"name": "MobileNetV1Enhance", "scale": 0.5},
                    "Neck": {"name": "SequenceEncoder", "encoder_type": "svtr", "dims": 64},
                    "Head": {"name": "CTCHead", "fc_decay": 0.00001},
                },
                "Loss": {"name": "CTCLoss"},
                "PostProcess": {"name": "CTCLabelDecode"},
                "Metric": {"name": "RecMetric", "main_indicator": "acc"},
            }
        else:
            return {
                "Global": {"use_gpu": True},
                "Architecture": {
                    "model_type": "det",
                    "algorithm": "DB",
                    "Backbone": {"name": "MobileNetV3", "scale": 0.5, "model_name": "large"},
                    "Neck": {"name": "DBFPN", "out_channels": 256},
                    "Head": {"name": "DBHead", "k": 50},
                },
                "Loss": {"name": "DBLoss"},
                "PostProcess": {"name": "DBPostProcess", "thresh": 0.3, "box_thresh": 0.6},
                "Metric": {"name": "DetMetric", "main_indicator": "hmean"},
            }
