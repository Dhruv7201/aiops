"""CLI command for the web annotation server."""

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(no_args_is_help=True)
console = Console()


def _lan_ip() -> str:
    """Best-effort LAN IP (UDP socket trick, no packets sent)."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="Bind address")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Port")] = 8765,
    annotate_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Registry dir (default: data/annotate)"),
    ] = None,
):
    """Serve the web annotation UI on the local network."""
    try:
        import uvicorn

        from aiops.annotate.server import create_app
    except ImportError:
        rprint(
            "[red]FastAPI/uvicorn not installed. "
            "Install with: pip install 'aiops[annotate]'[/red]"
        )
        raise typer.Exit(1)

    rprint(Panel.fit(
        f"[bold cyan]aiops annotate[/bold cyan]\n"
        f"Local:   [bold]http://localhost:{port}[/bold]\n"
        f"Network: [bold]http://{_lan_ip()}:{port}[/bold]",
        border_style="cyan",
    ))

    uvicorn.run(create_app(annotate_dir), host=host, port=port, log_level="info")


@app.command()
def start(
    host: Annotated[str, typer.Option("--host", help="Bind address")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="API server port")] = 8765,
    frontend_port: Annotated[
        int, typer.Option("--frontend-port", help="Vite dev server port")
    ] = 5173,
    frontend_dir: Annotated[
        Path, typer.Option("--frontend-dir", help="Frontend project directory")
    ] = Path("frontend"),
    annotate_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Registry dir (default: data/annotate)"),
    ] = None,
):
    """Run the API server AND the Vite dev frontend together on the network."""
    import os
    import shutil
    import subprocess

    try:
        import uvicorn

        from aiops.annotate.server import create_app
    except ImportError:
        rprint(
            "[red]FastAPI/uvicorn not installed. "
            "Install with: pip install 'aiops[annotate]'[/red]"
        )
        raise typer.Exit(1)

    frontend_dir = frontend_dir.expanduser().resolve()
    if not (frontend_dir / "package.json").exists():
        rprint(
            f"[red]No frontend project at {frontend_dir}.[/red] "
            "Run from the repo root or pass --frontend-dir."
        )
        raise typer.Exit(1)

    npm = shutil.which("npm")
    if npm is None:
        rprint("[red]npm not found on PATH — install Node.js (or load nvm) first.[/red]")
        raise typer.Exit(1)

    if not (frontend_dir / "node_modules").exists():
        with console.status("[bold green]Installing frontend dependencies (npm install)..."):
            subprocess.run([npm, "install"], cwd=frontend_dir, check=True)

    # Vite proxies /api to the backend; keep the target in sync with --port
    env = {**os.environ, "AIOPS_API_PORT": str(port)}
    vite = subprocess.Popen(
        [npm, "run", "dev", "--", "--host", host, "--port", str(frontend_port)],
        cwd=frontend_dir,
        env=env,
    )

    lan = _lan_ip()
    rprint(Panel.fit(
        f"[bold cyan]aiops annotate (dev)[/bold cyan]\n"
        f"UI (vite):  [bold]http://localhost:{frontend_port}[/bold]  ·  "
        f"[bold]http://{lan}:{frontend_port}[/bold]\n"
        f"API:        [bold]http://localhost:{port}[/bold]  ·  "
        f"[bold]http://{lan}:{port}[/bold]",
        border_style="cyan",
    ))

    try:
        uvicorn.run(create_app(annotate_dir), host=host, port=port, log_level="info")
    finally:
        if vite.poll() is None:
            vite.terminate()
            try:
                vite.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vite.kill()
