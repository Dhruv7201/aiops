"""CLI command for interactive fullstack project generation."""

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(no_args_is_help=True)
console = Console()

# -- Choices --

BACKEND_CHOICES = {
    "FastAPI": "fastapi",
    "Flask": "flask",
    "Django": "django",
}

VITE_TEMPLATE_CHOICES = {
    "React + TypeScript": "react-ts",
    "React + TypeScript + SWC": "react-swc-ts",
    "React": "react",
    "React + SWC": "react-swc",
    "Vue + TypeScript": "vue-ts",
    "Vue": "vue",
    "Svelte + TypeScript": "svelte-ts",
    "Vanilla + TypeScript": "vanilla-ts",
}

DATABASE_CHOICES = {
    "PostgreSQL": "postgresql",
    "MySQL": "mysql",
    "MongoDB": "mongodb",
    "Redis": "redis",
    "MSSQL": "mssql",
    "None": "none",
}

DB_DRIVERS = {
    "postgresql": {
        "SQLAlchemy (asyncpg)": "postgresql+asyncpg",
        "SQLAlchemy (psycopg2)": "postgresql+psycopg2",
        "Raw asyncpg": "postgresql",
    },
    "mysql": {
        "SQLAlchemy (aiomysql)": "mysql+aiomysql",
        "SQLAlchemy (pymysql)": "mysql+pymysql",
        "Raw aiomysql": "mysql",
    },
    "mssql": {
        "SQLAlchemy (pymssql)": "mssql+pymssql",
        "Raw pymssql": "mssql",
    },
    "mongodb": {
        "Motor (async)": "mongodb",
    },
    "redis": {
        "redis-py (async)": "redis",
    },
}

DB_METHOD_CHOICES = {
    "SQLAlchemy ORM": "sqlalchemy",
    "Connection string (raw driver)": "connstring",
}

FRONTEND_ADDONS = {
    "Tailwind CSS": "Utility-first CSS framework",
    "React Router": "Client-side routing",
    "shadcn/ui": "Reusable UI components (requires Tailwind)",
}


def _ask_select(message: str, choices: list[str]) -> str:
    import questionary

    return questionary.select(message, choices=choices, use_arrow_keys=True).ask()


def _ask_addons(addons: dict[str, str]) -> list[str]:
    """Ask for each addon individually with y/n, then confirm final selection."""
    selected: list[str] = []
    rprint("[dim]Select addons (Enter = Yes, n + Enter = No):[/dim]")

    for name, desc in addons.items():
        choice = _ask_confirm(f"  {name} — {desc}?", default=True)
        if choice is None:
            continue
        if choice:
            selected.append(name)

    if selected:
        rprint(f"\n[bold]Selected:[/bold] {', '.join(selected)}")
        proceed = _ask_confirm("Proceed with these addons?", default=True)
        if proceed is None or not proceed:
            # Let them re-pick
            return _ask_addons(addons)
    else:
        rprint("\n[dim]No addons selected.[/dim]")

    return selected


def _ask_confirm(message: str, default: bool = True) -> bool:
    import questionary

    return questionary.confirm(message, default=default).ask()


def _ask_text(message: str, default: str = "") -> str:
    import questionary

    return questionary.text(message, default=default).ask()


@app.command()
def fullstack(
    name: Annotated[str, typer.Argument(help="Project name")],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("."),
):
    """Interactively generate a fullstack project (backend + frontend + database)."""
    rprint(Panel.fit(
        f"[bold cyan]Fullstack Project Generator[/bold cyan]\n"
        f"Project: [bold]{name}[/bold]",
        border_style="cyan",
    ))

    root = Path(output) / name
    root.mkdir(parents=True, exist_ok=True)

    # -- Backend --
    rprint("\n[bold]Backend[/bold]")
    backend_label = _ask_select("Select backend framework:", list(BACKEND_CHOICES.keys()))
    if backend_label is None:
        raise typer.Abort()
    backend = BACKEND_CHOICES[backend_label]

    auth = _ask_confirm("Include authentication?", default=True)
    docker = _ask_confirm("Include Docker setup?", default=True)

    # -- Database --
    rprint("\n[bold]Database[/bold]")
    db_label = _ask_select("Select database:", list(DATABASE_CHOICES.keys()))
    if db_label is None:
        raise typer.Abort()
    db_type = DATABASE_CHOICES[db_label]

    db_url = ""
    db_method = "sqlalchemy"

    if db_type != "none":
        # Ask SQLAlchemy vs raw driver (only for SQL databases)
        if db_type in ("postgresql", "mysql", "mssql"):
            method_label = _ask_select("Database access method:", list(DB_METHOD_CHOICES.keys()))
            if method_label is None:
                raise typer.Abort()
            db_method = DB_METHOD_CHOICES[method_label]

        # Ask which driver
        drivers = DB_DRIVERS.get(db_type, {})
        if len(drivers) > 1:
            driver_label = _ask_select("Select driver:", list(drivers.keys()))
            if driver_label is None:
                raise typer.Abort()
            driver_scheme = drivers[driver_label]
        else:
            driver_scheme = list(drivers.values())[0]

        # Build default connection string
        defaults = {
            "postgresql": f"{driver_scheme}://user:pass@localhost:5432/{name}",
            "mysql": f"{driver_scheme}://user:pass@localhost:3306/{name}",
            "mssql": f"{driver_scheme}://sa:pass@localhost:1433/{name}",
            "mongodb": f"mongodb://localhost:27017/{name}",
            "redis": "redis://localhost:6379/0",
        }
        default_url = defaults.get(db_type, "")
        db_url = _ask_text("Connection string:", default=default_url)
        if db_url is None:
            raise typer.Abort()

    # -- Frontend --
    rprint("\n[bold]Frontend[/bold]")
    include_frontend = _ask_confirm("Include frontend?", default=True)

    frontend_template = "react-ts"
    frontend_addons: list[str] = []

    if include_frontend:
        template_label = _ask_select("Select Vite template:", list(VITE_TEMPLATE_CHOICES.keys()))
        if template_label is None:
            raise typer.Abort()
        frontend_template = VITE_TEMPLATE_CHOICES[template_label]

        rprint("\n[bold]Addons[/bold]")
        frontend_addons = _ask_addons(FRONTEND_ADDONS)

    # -- Summary --
    _print_summary(name, backend_label, db_label, db_url, db_method,
                   include_frontend, template_label if include_frontend else None,
                   frontend_addons, auth, docker)

    if not _ask_confirm("\nProceed with generation?", default=True):
        raise typer.Abort()

    # -- Generate --
    rprint()
    with console.status("[bold green]Generating project..."):
        # Backend
        from aiops.generators.backend import BackendGenerator
        backend_gen = BackendGenerator(backend)
        backend_dir = root / "backend"
        backend_gen.generate(
            "backend",
            output_dir=root,
            with_docker=docker,
            with_auth=auth,
            db_url=db_url or "sqlite:///db.sqlite3",
        )
        rprint(f"  [green]+ backend/[/green] ({backend_label})")

        # Frontend
        if include_frontend:
            from aiops.generators.frontend import FrontendGenerator
            frontend_gen = FrontendGenerator()
            frontend_gen.generate(
                "frontend",
                output_dir=root,
                template=frontend_template,
            )
            _apply_frontend_addons(root / "frontend", frontend_addons)
            rprint(f"  [green]+ frontend/[/green] ({template_label})")

        # Docker compose for the whole stack
        if docker:
            _gen_fullstack_compose(root, db_type, include_frontend)
            rprint(f"  [green]+ docker-compose.yml[/green]")

        # .env at project root
        env_lines = [f"PROJECT_NAME={name}"]
        if db_url:
            env_lines.append(f"DATABASE_URL={db_url}")
        (root / ".env").write_text("\n".join(env_lines) + "\n")
        rprint(f"  [green]+ .env[/green]")

    rprint(f"\n[bold green]Project generated at {root}[/bold green]")
    rprint(f"\n[bold]Next steps:[/bold]")
    rprint(f"  cd {root}")
    rprint(f"  # Backend:")
    rprint(f"  cd backend && pip install -r requirements.txt")
    if include_frontend:
        rprint(f"  # Frontend:")
        rprint(f"  cd frontend && npm install && npm run dev")
    if docker:
        rprint(f"  # Or just:")
        rprint(f"  docker compose up --build")


def _print_summary(
    name: str,
    backend: str,
    db: str,
    db_url: str,
    db_method: str,
    frontend: bool,
    template: str | None,
    addons: list[str],
    auth: bool,
    docker: bool,
) -> None:
    table = Table(title="Project Summary", show_header=False, border_style="cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    table.add_row("Project", name)
    table.add_row("Backend", backend)
    table.add_row("Auth", "Yes" if auth else "No")
    table.add_row("Database", f"{db} ({db_method})" if db != "None" else "None")
    if db_url:
        table.add_row("DB URL", db_url)
    table.add_row("Frontend", f"{template}" if frontend else "No")
    if addons:
        table.add_row("Addons", ", ".join(addons))
    table.add_row("Docker", "Yes" if docker else "No")

    console.print(table)


def _apply_frontend_addons(frontend_dir: Path, addons: list[str]) -> None:
    """Add selected frontend addons to package.json and config files."""
    pkg_path = frontend_dir / "package.json"
    if not pkg_path.exists():
        return

    import json
    pkg = json.loads(pkg_path.read_text())
    deps = pkg.setdefault("dependencies", {})
    dev_deps = pkg.setdefault("devDependencies", {})

    if "Tailwind CSS" in addons:
        dev_deps["tailwindcss"] = "^4.0.0"
        dev_deps["@tailwindcss/vite"] = "^4.0.0"

        # vite.config.ts integration
        vite_config = frontend_dir / "vite.config.ts"
        if vite_config.exists():
            content = vite_config.read_text()
            if "tailwindcss" not in content:
                content = content.replace(
                    "import react from '@vitejs/plugin-react'",
                    "import react from '@vitejs/plugin-react'\nimport tailwindcss from '@tailwindcss/vite'",
                ).replace(
                    "plugins: [react()]",
                    "plugins: [react(), tailwindcss()]",
                )
                vite_config.write_text(content)

        # Add @import to CSS
        css_path = frontend_dir / "src" / "index.css"
        if css_path.exists():
            content = css_path.read_text()
            if "@import" not in content:
                css_path.write_text(f'@import "tailwindcss";\n\n{content}')
        else:
            css_path.parent.mkdir(parents=True, exist_ok=True)
            css_path.write_text('@import "tailwindcss";\n')

    if "React Router" in addons:
        deps["react-router"] = "^7.0.0"

        # Add basic router setup
        router_file = frontend_dir / "src" / "router.tsx"
        router_file.write_text('''import { BrowserRouter, Routes, Route } from "react-router";

import App from "./App";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
      </Routes>
    </BrowserRouter>
  );
}
''')

    if "shadcn/ui" in addons:
        deps["class-variance-authority"] = "^0.7.0"
        deps["clsx"] = "^2.1.0"
        deps["tailwind-merge"] = "^2.2.0"
        deps["lucide-react"] = "^0.400.0"

        # cn utility
        lib_dir = frontend_dir / "src" / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        (lib_dir / "utils.ts").write_text('''import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
''')

        # components/ui directory
        ui_dir = frontend_dir / "src" / "components" / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)

        # Button component as starter
        (ui_dir / "button.tsx").write_text('''import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
''')

    pkg_path.write_text(json.dumps(pkg, indent=2) + "\n")


def _gen_fullstack_compose(root: Path, db_type: str, with_frontend: bool) -> None:
    """Generate a docker-compose.yml for the full stack."""
    services = """services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
"""

    if db_type == "postgresql":
        services += """    depends_on:
      - db

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: ${PROJECT_NAME:-app}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
"""
    elif db_type == "mysql":
        services += """    depends_on:
      - db

  db:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: pass
      MYSQL_USER: user
      MYSQL_PASSWORD: pass
      MYSQL_DATABASE: ${PROJECT_NAME:-app}
    ports:
      - "3306:3306"
    volumes:
      - mysqldata:/var/lib/mysql
"""
    elif db_type == "mongodb":
        services += """    depends_on:
      - db

  db:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongodata:/data/db
"""
    elif db_type == "redis":
        services += """    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
"""

    if with_frontend:
        services += """
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
"""

    # Volumes
    volumes_map = {
        "postgresql": "pgdata",
        "mysql": "mysqldata",
        "mongodb": "mongodata",
    }
    if db_type in volumes_map:
        services += f"""
volumes:
  {volumes_map[db_type]}:
"""

    (root / "docker-compose.yml").write_text(services)
