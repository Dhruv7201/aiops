# aiops

Production-grade ML engineer utility library for Computer Vision, backend systems, and data pipelines.

Docs: [USAGE.md](USAGE.md) (guide) · [COMMANDS.md](COMMANDS.md) (commands & settings reference).

## Install

```bash
# Quick setup
bash setup.sh

# Or manually
uv venv --python 3.12
uv pip install -e ".[dev]"
```

### Optional dependencies

```bash
uv pip install -e ".[paddle]"      # PaddleOCR
uv pip install -e ".[easyocr]"     # EasyOCR
uv pip install -e ".[tesseract]"   # Tesseract
uv pip install -e ".[yolo]"        # YOLO (Ultralytics)
uv pip install -e ".[postgres]"    # PostgreSQL
uv pip install -e ".[redis]"       # Redis
uv pip install -e ".[mongo]"       # MongoDB
uv pip install -e ".[mysql]"       # MySQL
uv pip install -e ".[mssql]"       # MSSQL
uv pip install -e ".[annotate]"    # Web annotation tool (FastAPI + uvicorn)
uv pip install -e ".[all]"         # Everything
```

## Usage

### CLI

```bash
aiops ocr detect image.png --engine paddle
aiops yolo predict photo.jpg --model yolov8n.pt --conf 0.5
aiops db connect "postgresql://user:pass@localhost/mydb"
aiops generate fullstack my_app    # interactive wizard: backend + frontend + db
aiops annotate serve               # web annotation UI on http://<lan-ip>:8765
```

### Annotation tool

LabelMe-style web annotation UI, shareable across the LAN (`make frontend` once to build the UI):

```bash
aiops annotate serve --port 8765   # serve built UI + API on one port
aiops annotate start               # dev mode: API + Vite dev server (HMR), both on 0.0.0.0
```

- Home screen with user creation/selection and projects (a project = a directory of images)
- Divide images among users (round-robin) with per-user queues and manual reassignment
- Rectangle + polygon tools, vertex editing, undo/redo, copy/paste (also across images),
  zoom/pan, keyboard shortcuts, autosave
- Annotations saved as LabelMe-compatible JSON in `<images_dir>/.annotations/`
- Export to LabelMe, YOLO (txt + dataset.yaml), or COCO (RF-DETR layout) with
  configurable train/val(/test) split ratios

### Python API

```python
# OCR
from aiops.ocr import OCR

ocr = OCR(engine="paddle")
results = ocr.detect("image.png", return_text=True, return_score=True, return_bbox=True)

# YOLO
from aiops.vision import YOLODetector

detector = YOLODetector(model="yolov8n.pt")
detections = detector.predict("photo.jpg", conf=0.5)

# Database
from aiops.db import Database

async with Database(url="postgresql://user:pass@localhost/mydb") as db:
    rows = await db.fetch("SELECT * FROM users")

# Image preprocessing
from aiops.vision import ImagePreprocessor

result = (
    ImagePreprocessor()
    .load("scan.png")
    .grayscale()
    .denoise(strength=10)
    .adaptive_threshold(block_size=11, c=2)
    .save("cleaned.png")
    .result()
)
```

## Development

```bash
make install    # Install with dev deps
make test       # Run tests
make lint       # Run linter
make format     # Format code
make build      # Build package
make clean      # Remove artifacts
```

## Project Structure

```
src/aiops/
├── core/           # Config, logging, plugin system, types
├── ocr/            # Unified OCR (PaddleOCR, EasyOCR, Tesseract)
│   └── training/   # Training pipelines per engine
├── vision/         # YOLO, ROI selector, preprocessing, dataset tools
├── annotate/       # Web-based multi-user annotation tool (LabelMe-style)
├── db/             # Async database connectors (Postgres, MySQL, MSSQL, Mongo, Redis)
├── generators/     # Backend/frontend project scaffolding
└── cli/            # Typer CLI commands
```
