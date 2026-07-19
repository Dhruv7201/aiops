# aiops — Command Reference & Usage Guide

All commands for the `aiops` CLI, the annotation web tool, and the repo's dev workflow.

## Setup

```bash
bash setup.sh                        # guided: venv + dev deps (+ optionally all extras)

# Or manually
uv venv --python 3.12
uv pip install -e ".[dev]"           # core + test/lint tools
```

### Optional dependency extras

```bash
uv pip install -e ".[paddle]"        # PaddleOCR (+ paddlepaddle)
uv pip install -e ".[easyocr]"       # EasyOCR
uv pip install -e ".[tesseract]"     # pytesseract (needs tesseract binary installed)
uv pip install -e ".[all-ocr]"       # all three OCR engines
uv pip install -e ".[yolo]"          # Ultralytics YOLO
uv pip install -e ".[postgres]"      # asyncpg + psycopg2
uv pip install -e ".[mysql]"         # aiomysql
uv pip install -e ".[mssql]"         # pymssql
uv pip install -e ".[mongo]"         # motor
uv pip install -e ".[redis]"         # redis + hiredis
uv pip install -e ".[all-db]"        # all database backends
uv pip install -e ".[annotate]"      # FastAPI + uvicorn for the annotation server
uv pip install -e ".[all]"           # everything
```

## CLI overview

```bash
aiops --help                         # top-level help
aiops version                        # print library version
```

Subcommand groups: `ocr`, `yolo`, `db`, `generate`, `annotate`.

## OCR — `aiops ocr`

```bash
aiops ocr detect IMAGE               # run OCR on an image (default engine: paddle)
  -e, --engine TEXT                  #   paddle | easyocr | tesseract
  -l, --lang TEXT                    #   language ("en" works for all engines,
                                     #   2-letter codes auto-map for tesseract)
  --text / --no-text                 #   include detected text (default: on)
  --score / --no-score               #   include confidence scores (default: on)
  --bbox / --no-bbox                 #   include bounding boxes (default: on)
  -o, --output PATH                  #   also save results as JSON

aiops ocr engines                    # list available OCR engines

aiops ocr train                      # train/fine-tune an OCR model
  -e, --engine TEXT                  #   paddle | easyocr | tesseract
  -d, --dataset PATH                 #   dataset directory (default: dataset)
  -o, --output PATH                  #   output directory (default: output)
  --epochs INT                       #   training epochs (default: 100)
```

Examples:

```bash
aiops ocr detect receipt.png --engine tesseract --lang en
aiops ocr detect scan.jpg -e paddle --no-bbox -o results.json
```

## YOLO — `aiops yolo`

```bash
aiops yolo predict IMAGE             # object detection on an image
  -m, --model TEXT                   #   model weights (default: yolov8n.pt)
  --conf FLOAT                       #   confidence threshold (default: 0.25)
  --device TEXT                      #   cpu | cuda | mps (default: cpu)
  -s, --save PATH                    #   save annotated image

aiops yolo train DATASET_YAML        # train on a YOLO dataset
  -m, --model TEXT                   #   base weights (default: yolov8n.pt)
  --epochs INT                       #   (default: 50)
  --imgsz INT                        #   input size (default: 640)
  --batch INT                        #   batch size (default: 16)
  --device TEXT                      #   (default: cpu)
  --name TEXT                        #   experiment name (default: train)

aiops yolo benchmark IMAGE           # measure inference speed (avg/fps/min/max)
  -m, --model TEXT  --runs INT  --device TEXT

aiops yolo convert-voc VOC_DIR       # Pascal VOC XML → YOLO txt labels
  -o, --output PATH                  #   (default: labels_yolo)

aiops yolo convert-coco COCO_JSON    # COCO JSON → YOLO txt labels (+ classes.txt)
  -o, --output PATH                  #   (default: labels_yolo)
```

Examples:

```bash
aiops yolo predict photo.jpg -m yolov8s.pt --conf 0.5 -s annotated.jpg
aiops yolo train dataset.yaml --epochs 100 --device cuda
```

## Database — `aiops db`

```bash
aiops db connect URL                 # test a connection
aiops db query SQL -u URL            # run a query, print a table
  --limit INT                        #   appended LIMIT (default: 50)
aiops db backends                    # list registered backends
```

Supported URL schemes: `postgresql://` (`postgres://`), `mysql://`, `mssql://`,
`mongodb://` (`mongo://`), `redis://` (`rediss://`).

```bash
aiops db connect "postgresql://user:pass@localhost/mydb"
aiops db query "SELECT * FROM users" -u "mysql://root@localhost/app" --limit 10
```

## Project generator — `aiops generate`

```bash
aiops generate fullstack NAME        # interactive wizard: backend + frontend + db
  -o, --output PATH                  #   parent directory (default: .)
```

The wizard walks through backend framework (FastAPI/Flask/Django), database +
connection string, Vite frontend template, addons (Tailwind, React Router,
shadcn/ui, …), auth, and Docker. It writes `backend/`, optional `frontend/`,
`docker-compose.yml`, and `.env` under `NAME/`.

## Annotation tool — `aiops annotate`

```bash
aiops annotate serve                 # serve API + built frontend (production-style)
  --host TEXT                        #   bind address (default: 0.0.0.0)
  -p, --port INT                     #   (default: 8765)
  -d, --dir PATH                     #   registry dir (default: data/annotate)

aiops annotate start                 # dev mode: API + Vite dev server together
  --host TEXT  -p, --port INT        #   as above
  --frontend-port INT                #   Vite port (default: 5173)
  --frontend-dir PATH                #   frontend project (default: frontend)
  -d, --dir PATH                     #   registry dir
```

`serve` needs the frontend built once (`make frontend`); `start` runs the Vite dev
server with `/api` proxied and hot reload. Both print the LAN URL for teammates.

### Web workflow

1. Open the printed URL, pick or create a **user**.
2. **New project** → point it at a directory of images on the server machine.
3. **Labels…** → define classes and colors.
4. **Assign images…** → round-robin split among selected users.
5. Annotate in the editor (see shortcuts below); saves are automatic on navigation.
6. **Export…** → choose format, split ratios, and output directory.

### Export formats

| Format | Layout |
|---|---|
| LabelMe | `<split>/images/` + `<split>/labels/*.json` |
| YOLO | `<split>/images/` + `<split>/labels/*.txt` + `dataset.yaml` (polygons → bboxes) |
| COCO (RF-DETR) | `train/`, `valid/`, `test/` each with images + `_annotations.coco.json` |

### Editor keyboard shortcuts

| Key | Action |
|---|---|
| `R` / `P` / `S` | rectangle / polygon / select tool |
| `1`–`9` | pick the Nth project label |
| click, double-click or click first point | polygon: add point, close |
| `Backspace` | polygon draft: remove last point |
| `Esc` | cancel draft / back to select |
| `Ctrl+Z` / `Ctrl+Shift+Z` or `Ctrl+Y` | undo / redo |
| `Ctrl+C` / `Ctrl+V` | copy / paste selected shapes |
| `Ctrl+S` | save |
| `Delete` | delete selected shapes |
| `←`/`A`, `→`/`D` | previous / next image (autosaves) |
| `Space`+drag, wheel | pan, zoom |

### REST API (base: `http://host:8765`)

| Method & path | Purpose |
|---|---|
| `GET /api/health` | health check |
| `GET` / `POST /api/users` | list / add users |
| `GET` / `POST /api/projects` | list / create projects |
| `GET` / `PATCH` / `DELETE /api/projects/{name}` | get / rename / unregister (annotations kept on disk) |
| `PUT /api/projects/{name}/labels` | set label definitions |
| `GET /api/projects/{name}/images` | list images with status |
| `GET /api/projects/{name}/images/{file}` | fetch an image |
| `POST` / `PUT /api/projects/{name}/assign` | bulk round-robin / single reassign |
| `GET` / `PUT /api/projects/{name}/annotations/{file}` | load / save a LabelMe doc |
| `POST /api/projects/{name}/export` | export (`format`: `labelme` \| `yolo` \| `coco`) |

## Configuration (env vars / `.env`)

All settings use the `AIOPS_` prefix, e.g.:

```bash
AIOPS_LOG_LEVEL=DEBUG
AIOPS_OCR_ENGINE=easyocr             # default OCR engine
AIOPS_YOLO_MODEL=yolov8s.pt
AIOPS_YOLO_DEVICE=cuda
AIOPS_DATABASE_URL=postgresql://localhost/app
AIOPS_ANNOTATE_DIR=data/annotate     # project registry location
AIOPS_ANNOTATE_PORT=8765
```

## Development (`make` targets)

```bash
make install            # venv + dev deps
make install-all        # venv + every optional extra
make test               # pytest
make test-cov           # pytest with coverage
make lint               # ruff check
make format             # ruff format
make check              # lint + test
make frontend-install   # npm ci in frontend/
make frontend           # build SPA into src/aiops/annotate/static
make frontend-dev       # Vite dev server only
make annotate-serve     # run the annotation server
make annotate-start     # backend + Vite dev frontend together
make build              # frontend build + uv build (wheel/sdist)
make publish            # build + publish to PyPI
make clean              # remove build artifacts and caches
```
