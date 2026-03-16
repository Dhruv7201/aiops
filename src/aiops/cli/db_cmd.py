"""CLI commands for database operations."""

import asyncio
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def connect(
    url: Annotated[str, typer.Argument(help="Database connection URL")],
):
    """Test database connection."""
    from aiops.db import Database

    async def _test():
        db = Database(url=url)
        try:
            await db.connect()
            rprint("[green]Connection successful![/green]")
            await db.disconnect()
        except Exception as e:
            rprint(f"[red]Connection failed: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(_test())


@app.command()
def query(
    url: Annotated[str, typer.Option("--url", "-u", help="Database URL")],
    sql: Annotated[str, typer.Argument(help="SQL query to execute")],
    limit: Annotated[int, typer.Option("--limit")] = 50,
):
    """Execute a query and display results."""
    from aiops.db import Database

    async def _query():
        async with Database(url=url) as db:
            if limit:
                sql_with_limit = f"{sql.rstrip(';')} LIMIT {limit}"
            else:
                sql_with_limit = sql
            rows = await db.fetch(sql_with_limit)

        if not rows:
            rprint("[yellow]No results.[/yellow]")
            return

        table = Table()
        for col in rows[0].keys():
            table.add_column(str(col))
        for row in rows:
            table.add_row(*[str(v) for v in row.values()])
        console.print(table)
        rprint(f"[dim]{len(rows)} rows[/dim]")

    asyncio.run(_query())


@app.command()
def backends():
    """List available database backends."""
    from aiops.db import Database

    rprint("[bold]Available database backends:[/bold]")
    for backend in Database.available_backends():
        rprint(f"  - {backend}")
