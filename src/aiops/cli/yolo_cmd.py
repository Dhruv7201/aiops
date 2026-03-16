"""CLI commands for YOLO operations."""

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def predict(
    image: Annotated[Path, typer.Argument(help="Path to image")],
    model: Annotated[str, typer.Option("--model", "-m")] = "yolov8n.pt",
    conf: Annotated[float, typer.Option("--conf")] = 0.25,
    device: Annotated[str, typer.Option("--device")] = "cpu",
    save: Annotated[Path | None, typer.Option("--save", "-s", help="Save annotated image")] = None,
):
    """Run YOLO detection on an image."""
    from aiops.vision import YOLODetector

    if not image.exists():
        rprint(f"[red]Error: Image not found: {image}[/red]")
        raise typer.Exit(1)

    with console.status("Running detection..."):
        detector = YOLODetector(model=model, device=device)
        results = detector.predict(str(image), conf=conf)

    if not results:
        rprint("[yellow]No objects detected.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Detection Results")
    table.add_column("Class", style="cyan")
    table.add_column("Confidence", style="green")
    table.add_column("BBox (xyxy)", style="dim")

    for det in results:
        bbox_str = ", ".join(f"{v:.1f}" for v in det.bbox)
        table.add_row(det.class_name, f"{det.confidence:.3f}", bbox_str)

    console.print(table)
    rprint(f"[bold]{len(results)} objects detected[/bold]")

    if save:
        import cv2

        vis = detector.visualize(str(image), results)
        cv2.imwrite(str(save), vis)
        rprint(f"[green]Saved annotated image to {save}[/green]")


@app.command()
def train(
    dataset: Annotated[Path, typer.Argument(help="Path to dataset YAML")],
    model: Annotated[str, typer.Option("--model", "-m")] = "yolov8n.pt",
    epochs: Annotated[int, typer.Option("--epochs")] = 50,
    imgsz: Annotated[int, typer.Option("--imgsz")] = 640,
    batch: Annotated[int, typer.Option("--batch")] = 16,
    device: Annotated[str, typer.Option("--device")] = "cpu",
    name: Annotated[str, typer.Option("--name")] = "train",
):
    """Train a YOLO model."""
    from aiops.vision import YOLODetector

    rprint(f"[bold]Training YOLO model: {model}[/bold]")
    detector = YOLODetector(model=model, device=device)
    detector.train(dataset=dataset, epochs=epochs, imgsz=imgsz, batch=batch, name=name)
    rprint("[green]Training complete![/green]")


@app.command()
def benchmark(
    image: Annotated[Path, typer.Argument(help="Path to image")],
    model: Annotated[str, typer.Option("--model", "-m")] = "yolov8n.pt",
    runs: Annotated[int, typer.Option("--runs")] = 100,
    device: Annotated[str, typer.Option("--device")] = "cpu",
):
    """Benchmark YOLO inference speed."""
    from aiops.vision import YOLODetector

    with console.status(f"Benchmarking ({runs} runs)..."):
        detector = YOLODetector(model=model, device=device)
        stats = detector.benchmark(str(image), runs=runs)

    rprint(f"[bold]Benchmark Results ({model}):[/bold]")
    rprint(f"  Avg: [cyan]{stats['avg_ms']:.1f}ms[/cyan]")
    rprint(f"  FPS: [green]{stats['fps']:.1f}[/green]")
    rprint(f"  Min: {stats['min_ms']:.1f}ms | Max: {stats['max_ms']:.1f}ms")


@app.command("convert-voc")
def convert_voc(
    voc_dir: Annotated[Path, typer.Argument(help="VOC annotations directory")],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("labels_yolo"),
):
    """Convert Pascal VOC annotations to YOLO format."""
    from aiops.vision.dataset import voc_to_yolo

    voc_to_yolo(voc_dir, output)
    rprint(f"[green]Converted to YOLO format: {output}[/green]")


@app.command("convert-coco")
def convert_coco(
    coco_json: Annotated[Path, typer.Argument(help="COCO JSON annotation file")],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("labels_yolo"),
):
    """Convert COCO JSON annotations to YOLO format."""
    from aiops.vision.dataset import coco_to_yolo

    coco_to_yolo(coco_json, output)
    rprint(f"[green]Converted to YOLO format: {output}[/green]")
