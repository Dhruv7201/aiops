# aiops — Commands & Settings Reference

Terse reference: every command with its flags and defaults, plus all settings.
For the narrative guide (workflows, export layouts, API), see [USAGE.md](USAGE.md).

## CLI commands

```text
aiops version
aiops --help                                  # help works on every level

aiops ocr detect IMAGE
    -e, --engine TEXT        paddle           # paddle | easyocr | tesseract
    -l, --lang TEXT          en
    --text / --no-text       on
    --score / --no-score     on
    --bbox / --no-bbox       on
    -o, --output PATH        -                # save results JSON
aiops ocr engines
aiops ocr train
    -e, --engine TEXT        paddle
    -d, --dataset PATH       dataset
    -o, --output PATH        output
    --epochs INT             100

aiops yolo predict IMAGE
    -m, --model TEXT         yolov8n.pt
    --conf FLOAT             0.25
    --device TEXT            cpu
    -s, --save PATH          -                # save annotated image
aiops yolo train DATASET_YAML
    -m, --model TEXT         yolov8n.pt
    --epochs INT             50
    --imgsz INT              640
    --batch INT              16
    --device TEXT            cpu
    --name TEXT              train
aiops yolo benchmark IMAGE
    -m, --model TEXT         yolov8n.pt
    --runs INT               100
    --device TEXT            cpu
aiops yolo convert-voc VOC_DIR
    -o, --output PATH        labels_yolo
aiops yolo convert-coco COCO_JSON
    -o, --output PATH        labels_yolo

aiops db connect URL
aiops db query SQL
    -u, --url TEXT           (required)
    --limit INT              50
aiops db backends

aiops generate fullstack NAME
    -o, --output PATH        .                # interactive wizard

aiops annotate serve
    --host TEXT              0.0.0.0
    -p, --port INT           8765
    -d, --dir PATH           data/annotate
aiops annotate start
    --host TEXT              0.0.0.0
    -p, --port INT           8765
    --frontend-port INT      5173
    --frontend-dir PATH      frontend
    -d, --dir PATH           data/annotate
```

## Make targets

```text
make install            venv + dev deps
make install-all        venv + every optional extra
make test               pytest
make test-cov           pytest + coverage
make lint               ruff check
make format             ruff format
make check              lint + test
make frontend-install   npm ci in frontend/
make frontend           build SPA into src/aiops/annotate/static
make frontend-dev       Vite dev server only
make annotate-serve     run annotation server
make annotate-start     backend + Vite dev frontend
make build              frontend build + wheel/sdist
make publish            build + publish to PyPI
make clean              remove build artifacts and caches
```

## Settings

Loaded from environment variables or a `.env` file; prefix `AIOPS_`.

| Env var | Default | Purpose |
|---|---|---|
| `AIOPS_DEBUG` | `false` | debug mode |
| `AIOPS_LOG_LEVEL` | `INFO` | logging level |
| `AIOPS_DATA_DIR` | `data` | data directory |
| `AIOPS_MODELS_DIR` | `models` | model storage directory |
| `AIOPS_OCR_ENGINE` | `paddle` | default OCR engine |
| `AIOPS_OCR_LANG` | `en` | default OCR language |
| `AIOPS_DATABASE_URL` | *(empty)* | default SQL database URL |
| `AIOPS_REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `AIOPS_MONGO_URL` | `mongodb://localhost:27017` | MongoDB URL |
| `AIOPS_YOLO_MODEL` | `yolov8n.pt` | default YOLO weights |
| `AIOPS_YOLO_DEVICE` | `cpu` | default YOLO device |
| `AIOPS_ANNOTATE_DIR` | `data/annotate` | annotation project registry |
| `AIOPS_ANNOTATE_HOST` | `0.0.0.0` | annotation server bind address |
| `AIOPS_ANNOTATE_PORT` | `8765` | annotation server port |

Database URL schemes: `postgresql://` (`postgres://`), `mysql://`, `mssql://`,
`mongodb://` (`mongo://`), `redis://` (`rediss://`).
