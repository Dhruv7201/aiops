"""Quick demo of the aiops library."""

from aiops import __version__


def main():
    print(f"aiops v{__version__}")
    print()

    # Show available modules
    print("Available modules:")
    print("  - aiops.ocr        → Unified OCR (PaddleOCR, EasyOCR, Tesseract)")
    print("  - aiops.vision     → YOLO, ROI selector, image preprocessing")
    print("  - aiops.db         → Async database connectors (PG, MySQL, MSSQL, Mongo, Redis)")
    print("  - aiops.generators → Backend & frontend project scaffolding")
    print("  - aiops.cli        → CLI tool (run: aiops --help)")
    print()

    # Example: image preprocessing pipeline
    print("Example usage:")
    print("""
    from aiops.ocr import OCR
    from aiops.vision import YOLODetector, ImagePreprocessor
    from aiops.db import Database

    # OCR
    ocr = OCR(engine="paddle")
    results = ocr.detect("invoice.png", return_text=True, return_score=True)

    # YOLO
    detector = YOLODetector(model="yolov8n.pt")
    detections = detector.predict("photo.jpg")

    # Database
    async with Database(url="postgresql://user:pass@localhost/db") as db:
        rows = await db.fetch("SELECT * FROM users")

    # CLI
    # $ aiops ocr detect image.png --engine paddle
    # $ aiops yolo predict image.jpg --model yolov8n.pt
    # $ aiops generate backend my_api --framework fastapi
    """)


if __name__ == "__main__":
    main()
