"""CLI commands for OCR operations."""

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def detect(
    image: Annotated[Path, typer.Argument(help="Path to image file")],
    engine: Annotated[str, typer.Option("--engine", "-e", help="OCR engine")] = "paddle",
    lang: Annotated[str, typer.Option("--lang", "-l", help="Language")] = "en",
    text: Annotated[bool, typer.Option("--text/--no-text", help="Include text")] = True,
    score: Annotated[bool, typer.Option("--score/--no-score", help="Include scores")] = True,
    bbox: Annotated[bool, typer.Option("--bbox/--no-bbox", help="Include bounding boxes")] = True,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Save results to JSON")] = None,
):
    """Run OCR detection on an image."""
    from aiops.ocr import OCR

    if not image.exists():
        rprint(f"[red]Error: Image not found: {image}[/red]")
        raise typer.Exit(1)

    with console.status(f"Running OCR ({engine})..."):
        ocr = OCR(engine=engine, lang=lang)
        results = ocr.detect(str(image), return_text=text, return_score=score, return_bbox=bbox)

    if not results:
        rprint("[yellow]No text detected.[/yellow]")
        raise typer.Exit(0)

    # Display results as table
    table = Table(title=f"OCR Results ({engine})")
    if text:
        table.add_column("Text", style="cyan")
    if score:
        table.add_column("Score", style="green")
    if bbox:
        table.add_column("BBox", style="dim")

    for r in results:
        row = []
        if text:
            row.append(r.get("text", ""))
        if score:
            row.append(f"{r.get('score', 0):.3f}")
        if bbox:
            row.append(str(r.get("bbox", "")))
        table.add_row(*row)

    console.print(table)

    if output:
        import json
        output.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        rprint(f"[green]Results saved to {output}[/green]")


@app.command()
def engines():
    """List available OCR engines."""
    from aiops.ocr import OCR

    rprint("[bold]Available OCR engines:[/bold]")
    for eng in OCR.available_engines():
        rprint(f"  - {eng}")


@app.command()
def train(
    engine: Annotated[str, typer.Option("--engine", "-e")] = "paddle",
    dataset: Annotated[Path, typer.Option("--dataset", "-d")] = Path("dataset"),
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("output"),
    epochs: Annotated[int, typer.Option("--epochs")] = 100,
):
    """Train an OCR model."""
    from aiops.ocr.training import PaddleTrainer, EasyOCRTrainer, TesseractTrainer

    trainers = {
        "paddle": PaddleTrainer,
        "easyocr": EasyOCRTrainer,
        "tesseract": TesseractTrainer,
    }

    if engine not in trainers:
        rprint(f"[red]Unknown engine: {engine}. Available: {list(trainers.keys())}[/red]")
        raise typer.Exit(1)

    rprint(f"[bold]Training {engine} model...[/bold]")
    trainer = trainers[engine](dataset_dir=dataset, output_dir=output)
    trainer.train(epochs=epochs)
    rprint(f"[green]Training complete. Output: {output}[/green]")
