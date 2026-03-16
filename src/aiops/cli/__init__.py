"""CLI entry point built with typer."""

import typer

from aiops.cli.ocr_cmd import app as ocr_app
from aiops.cli.yolo_cmd import app as yolo_app
from aiops.cli.db_cmd import app as db_app
from aiops.cli.generate_cmd import app as generate_app

app = typer.Typer(
    name="aiops",
    help="ML Engineer utility toolkit — OCR, YOLO, databases, project generators.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.add_typer(ocr_app, name="ocr", help="OCR detection and training")
app.add_typer(yolo_app, name="yolo", help="YOLO detection and training")
app.add_typer(db_app, name="db", help="Database operations")
app.add_typer(generate_app, name="generate", help="Generate fullstack projects")


@app.command()
def version():
    """Show library version."""
    from aiops import __version__

    typer.echo(f"aiops v{__version__}")
