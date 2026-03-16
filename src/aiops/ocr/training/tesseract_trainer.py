"""Tesseract OCR training pipeline.

Fine-tunes Tesseract 4/5 LSTM models.

Requirements:
    - tesseract >= 4.0 (with training tools)
    - Install training tools: apt install tesseract-ocr libtesseract-dev
    - Base traineddata from: https://github.com/tesseract-ocr/tessdata_best

Workflow:
    1. Prepare ground truth: .tif images + .gt.txt text files
    2. Generate .lstmf training files using tesseract
    3. Extract LSTM from base traineddata
    4. Fine-tune with lstmtraining
    5. Combine into final .traineddata with combine_tessdata
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from aiops.core.log import get_logger

logger = get_logger(__name__)


class TesseractTrainer:
    """Training pipeline for Tesseract LSTM fine-tuning.

    Expected dataset structure:
        dataset/
        ├── ground_truth/
        │   ├── image1.tif
        │   ├── image1.gt.txt    # single line: the text in the image
        │   ├── image2.tif
        │   └── image2.gt.txt
        └── tessdata/            # base traineddata files
            └── eng.traineddata  # from tessdata_best repo

    Usage:
        trainer = TesseractTrainer(
            dataset_dir="dataset/",
            lang="eng",
        )
        trainer.prepare_dataset("raw_images/", "raw_texts/")
        trainer.train(epochs=1000)
    """

    def __init__(
        self,
        dataset_dir: str | Path,
        output_dir: str | Path = "output",
        lang: str = "eng",
    ) -> None:
        self.dataset_dir = Path(dataset_dir)
        self.output_dir = Path(output_dir)
        self.lang = lang
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def prepare_dataset(
        self,
        images_dir: str | Path,
        texts_dir: str | Path,
        output_dir: str | Path | None = None,
    ) -> Path:
        """Convert image/text pairs to Tesseract ground truth format.

        Expects paired files:
            images_dir/image1.png  +  texts_dir/image1.txt

        Produces:
            ground_truth/lang.image1.tif  +  ground_truth/lang.image1.gt.txt

        Tesseract requires the naming convention: lang.basename.tif / lang.basename.gt.txt
        """
        import cv2

        images = Path(images_dir)
        texts = Path(texts_dir)
        out = Path(output_dir or self.dataset_dir) / "ground_truth"
        out.mkdir(parents=True, exist_ok=True)

        count = 0
        for img_path in sorted(images.glob("*")):
            if img_path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
                continue

            txt_path = texts / f"{img_path.stem}.txt"
            if not txt_path.exists():
                logger.warning(f"No text file for {img_path.name}, skipping")
                continue

            # Tesseract naming: lang.basename.tif
            base_name = f"{self.lang}.{img_path.stem}"
            tif_path = out / f"{base_name}.tif"
            gt_path = out / f"{base_name}.gt.txt"

            # Convert to TIFF (single-channel for better training)
            img = cv2.imread(str(img_path))
            cv2.imwrite(str(tif_path), img)
            shutil.copy2(txt_path, gt_path)
            count += 1

        logger.info(f"Prepared {count} ground truth pairs in {out}")
        return out

    def generate_lstmf(self, ground_truth_dir: str | Path | None = None) -> list[Path]:
        """Generate .lstmf training files from ground truth.

        Each .tif + .gt.txt pair produces a .lstmf file that the LSTM trainer reads.
        Requires the base traineddata in dataset/tessdata/.
        """
        gt_dir = Path(ground_truth_dir or self.dataset_dir / "ground_truth")
        tessdata_dir = self.dataset_dir / "tessdata"

        if not tessdata_dir.exists():
            raise FileNotFoundError(
                f"tessdata directory not found: {tessdata_dir}. "
                f"Download {self.lang}.traineddata from tessdata_best repo."
            )

        lstmf_files = []
        for tif in sorted(gt_dir.glob(f"{self.lang}.*.tif")):
            gt_txt = tif.with_suffix("").with_suffix(".gt.txt")
            if not gt_txt.exists():
                logger.warning(f"No .gt.txt for {tif.name}, skipping")
                continue

            # Generate .box and .lstmf in one step
            stem = tif.with_suffix("")  # e.g., /path/eng.image1
            cmd = [
                "tesseract", str(tif), str(stem),
                "--tessdata-dir", str(tessdata_dir),
                "--psm", "6",  # assume uniform block of text
                "lstm.train",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"lstmf generation failed for {tif.name}: {result.stderr.strip()}")
                continue

            lstmf = tif.with_suffix(".lstmf")
            if lstmf.exists():
                lstmf_files.append(lstmf)

        logger.info(f"Generated {len(lstmf_files)} .lstmf files")
        return lstmf_files

    def extract_lstm(self, traineddata_path: str | Path | None = None) -> Path:
        """Extract LSTM model from .traineddata for fine-tuning.

        Returns:
            Path to the extracted .lstm file.
        """
        traineddata = Path(
            traineddata_path or self.dataset_dir / "tessdata" / f"{self.lang}.traineddata"
        )
        if not traineddata.exists():
            raise FileNotFoundError(f"traineddata not found: {traineddata}")

        lstm_file = self.output_dir / f"{self.lang}.lstm"

        cmd = [
            "combine_tessdata", "-e",
            str(traineddata),
            str(lstm_file),
        ]
        logger.info(f"Extracting LSTM: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

        if not lstm_file.exists():
            raise RuntimeError(f"LSTM extraction failed — {lstm_file} not created")

        return lstm_file

    def train(
        self,
        epochs: int = 1000,
        learning_rate: float = 0.001,
        base_traineddata: str | Path | None = None,
        **kwargs: Any,
    ) -> Path:
        """Fine-tune Tesseract LSTM model.

        Steps:
        1. Generate .lstmf files if needed
        2. Extract LSTM from base model
        3. Run lstmtraining to fine-tune
        4. Combine into final .traineddata

        Args:
            epochs: max training iterations.
            learning_rate: training learning rate.
            base_traineddata: base .traineddata for fine-tuning.

        Returns:
            Path to the output .traineddata file.
        """
        tessdata_dir = self.dataset_dir / "tessdata"
        base = Path(base_traineddata or tessdata_dir / f"{self.lang}.traineddata")
        if not base.exists():
            raise FileNotFoundError(
                f"Base traineddata not found: {base}. "
                f"Download from https://github.com/tesseract-ocr/tessdata_best"
            )

        # Step 1: Generate lstmf files
        gt_dir = self.dataset_dir / "ground_truth"
        lstmf_files = list(gt_dir.glob("*.lstmf"))
        if not lstmf_files:
            lstmf_files = self.generate_lstmf(gt_dir)

        if not lstmf_files:
            raise RuntimeError("No .lstmf files generated. Check your ground truth data.")

        # Step 2: Write training file list
        list_file = self.output_dir / "training_files.txt"
        list_file.write_text("\n".join(str(f) for f in lstmf_files) + "\n")

        # Step 3: Extract LSTM from base model
        lstm_file = self.extract_lstm(base)

        # Step 4: Run lstmtraining
        checkpoint_prefix = self.output_dir / "checkpoints" / self.lang
        checkpoint_prefix.parent.mkdir(parents=True, exist_ok=True)

        train_cmd = [
            "lstmtraining",
            "--model_output", str(checkpoint_prefix),
            "--continue_from", str(lstm_file),
            "--traineddata", str(base),
            "--train_listfile", str(list_file),
            "--max_iterations", str(epochs),
            "--learning_rate", str(learning_rate),
        ]

        logger.info(f"Starting Tesseract training: {' '.join(train_cmd)}")
        subprocess.run(train_cmd, check=True)

        # Step 5: Combine checkpoint into final traineddata
        output_model = self.output_dir / f"{self.lang}.traineddata"
        checkpoint_file = Path(f"{checkpoint_prefix}_checkpoint")
        if not checkpoint_file.exists():
            # lstmtraining may use different naming
            candidates = list(checkpoint_prefix.parent.glob(f"{self.lang}*_checkpoint"))
            if candidates:
                checkpoint_file = candidates[0]
            else:
                raise RuntimeError(f"No checkpoint found at {checkpoint_prefix}_checkpoint")

        combine_cmd = [
            "lstmtraining",
            "--stop_training",
            "--continue_from", str(checkpoint_file),
            "--traineddata", str(base),
            "--model_output", str(output_model),
        ]

        logger.info(f"Combining model: {' '.join(combine_cmd)}")
        subprocess.run(combine_cmd, check=True)

        logger.info(f"Training complete: {output_model}")
        return output_model

    def evaluate(
        self,
        model_path: str | Path | None = None,
        test_images_dir: str | Path | None = None,
    ) -> dict[str, float]:
        """Evaluate trained model on test images.

        Simple accuracy check: run OCR on test images and compare to ground truth.

        Returns:
            Dict with accuracy metrics.
        """
        import cv2
        import pytesseract

        model = Path(model_path or self.output_dir / f"{self.lang}.traineddata")
        test_dir = Path(test_images_dir or self.dataset_dir / "ground_truth")

        # Copy model to a temp tessdata dir for pytesseract
        eval_tessdata = self.output_dir / "eval_tessdata"
        eval_tessdata.mkdir(exist_ok=True)
        shutil.copy2(model, eval_tessdata / f"{self.lang}.traineddata")

        correct = 0
        total = 0
        char_correct = 0
        char_total = 0

        for gt_file in sorted(test_dir.glob(f"{self.lang}.*.gt.txt")):
            tif = gt_file.with_suffix("").with_suffix(".tif")
            if not tif.exists():
                continue

            expected = gt_file.read_text().strip()
            img = cv2.imread(str(tif))
            predicted = pytesseract.image_to_string(
                img,
                lang=self.lang,
                config=f"--tessdata-dir {eval_tessdata} --psm 6",
            ).strip()

            total += 1
            if predicted == expected:
                correct += 1

            # Character-level accuracy
            for exp_c, pred_c in zip(expected, predicted):
                char_total += 1
                if exp_c == pred_c:
                    char_correct += 1
            char_total += abs(len(expected) - len(predicted))

        results = {
            "word_accuracy": correct / total if total else 0.0,
            "char_accuracy": char_correct / char_total if char_total else 0.0,
            "total_samples": total,
        }
        logger.info(f"Evaluation: {results}")
        return results
