"""Backend project generator for FastAPI, Flask, and Django."""

from __future__ import annotations

from pathlib import Path

from aiops.core.log import get_logger
from aiops.core.types import BackendFramework

logger = get_logger(__name__)


class BackendGenerator:
    """Generate production-ready backend project scaffolding.

    Usage:
        gen = BackendGenerator("fastapi")
        gen.generate("my_api", output_dir="projects/")
    """

    def __init__(self, framework: str = "fastapi") -> None:
        self.framework = BackendFramework(framework.lower())

    def generate(
        self,
        project_name: str,
        output_dir: str | Path = ".",
        *,
        with_docker: bool = True,
        with_auth: bool = True,
        db_url: str = "postgresql://user:pass@localhost/db",
    ) -> Path:
        root = Path(output_dir) / project_name
        root.mkdir(parents=True, exist_ok=True)

        generators = {
            BackendFramework.FASTAPI: self._gen_fastapi,
            BackendFramework.FLASK: self._gen_flask,
            BackendFramework.DJANGO: self._gen_django,
        }
        generators[self.framework](root, project_name, with_docker, with_auth, db_url)
        logger.info(f"Generated {self.framework} project at {root}")
        return root

    def _gen_fastapi(
        self, root: Path, name: str, docker: bool, auth: bool, db_url: str
    ) -> None:
        app_dir = root / "app"
        app_dir.mkdir(exist_ok=True)
        (app_dir / "routers").mkdir(exist_ok=True)
        (app_dir / "models").mkdir(exist_ok=True)
        (app_dir / "schemas").mkdir(exist_ok=True)
        (app_dir / "services").mkdir(exist_ok=True)

        # main.py
        (app_dir / "__init__.py").write_text("")
        (app_dir / "routers" / "__init__.py").write_text("")
        (app_dir / "models" / "__init__.py").write_text("")
        (app_dir / "schemas" / "__init__.py").write_text("")
        (app_dir / "services" / "__init__.py").write_text("")

        (app_dir / "main.py").write_text(f'''"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="{name}",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
''')

        (app_dir / "config.py").write_text(f'''"""Application settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "{name}"
    debug: bool = False
    database_url: str = "{db_url}"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
''')

        (app_dir / "database.py").write_text('''"""Async database setup with SQLAlchemy."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
''')

        (app_dir / "routers" / "health.py").write_text('''"""Health check router."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "ok"}
''')

        if auth:
            self._gen_fastapi_auth(app_dir)

        # Root files
        (root / "requirements.txt").write_text(
            "fastapi[standard]>=0.115\nuvicorn[standard]>=0.30\n"
            "sqlalchemy[asyncio]>=2.0\nasyncpg>=0.29\n"
            "pydantic-settings>=2.0\npython-jose[cryptography]>=3.3\n"
            "passlib[bcrypt]>=1.7\n"
        )

        (root / ".env").write_text(
            f"DATABASE_URL={db_url}\nSECRET_KEY=change-me\nDEBUG=true\n"
        )

        if docker:
            self._gen_dockerfile(root, "uvicorn app.main:app --host 0.0.0.0 --port 8000")

    def _gen_fastapi_auth(self, app_dir: Path) -> None:
        (app_dir / "auth.py").write_text('''"""JWT authentication utilities."""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return {"user_id": user_id, **payload}
    except JWTError:
        raise credentials_exception
''')

    def _gen_flask(
        self, root: Path, name: str, docker: bool, auth: bool, db_url: str
    ) -> None:
        app_dir = root / "app"
        app_dir.mkdir(exist_ok=True)
        (app_dir / "routes").mkdir(exist_ok=True)
        (app_dir / "models").mkdir(exist_ok=True)

        (app_dir / "__init__.py").write_text(f'''"""Flask application factory."""

from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "{db_url}"
    app.config["SECRET_KEY"] = "change-me-in-production"
    CORS(app)

    from app.routes.health import health_bp
    app.register_blueprint(health_bp)

    return app
''')

        (app_dir / "routes" / "__init__.py").write_text("")
        (app_dir / "routes" / "health.py").write_text('''"""Health check route."""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check():
    return jsonify({"status": "ok"})
''')
        (app_dir / "models" / "__init__.py").write_text("")

        (root / "run.py").write_text('''from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
''')

        (root / "requirements.txt").write_text(
            "flask>=3.0\nflask-cors>=4.0\nflask-sqlalchemy>=3.1\n"
            "psycopg2-binary>=2.9\ngunicorn>=22.0\n"
        )
        (root / ".env").write_text(f"DATABASE_URL={db_url}\nSECRET_KEY=change-me\n")

        if docker:
            self._gen_dockerfile(root, "gunicorn -b 0.0.0.0:5000 'app:create_app()'")

    def _gen_django(
        self, root: Path, name: str, docker: bool, auth: bool, db_url: str
    ) -> None:
        import subprocess

        subprocess.run(
            ["django-admin", "startproject", name, str(root)],
            check=False,
            capture_output=True,
        )

        (root / "requirements.txt").write_text(
            "django>=5.0\ndjango-cors-headers>=4.3\n"
            "psycopg2-binary>=2.9\ngunicorn>=22.0\n"
            "django-environ>=0.11\n"
        )
        (root / ".env").write_text(f"DATABASE_URL={db_url}\nSECRET_KEY=change-me\nDEBUG=True\n")

        if docker:
            self._gen_dockerfile(root, f"gunicorn -b 0.0.0.0:8000 {name}.wsgi:application")

    @staticmethod
    def _gen_dockerfile(root: Path, cmd: str) -> None:
        (root / "Dockerfile").write_text(f'''FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD {cmd.split()}
''')

        (root / "docker-compose.yml").write_text('''services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
''')

        (root / ".dockerignore").write_text(
            "__pycache__\n*.pyc\n.env\n.git\n.venv\nnode_modules\n"
        )
