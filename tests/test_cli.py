"""Tests for CLI commands."""

from typer.testing import CliRunner

from aiops.cli import app

runner = CliRunner()


class TestCLI:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "aiops" in result.output

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ocr" in result.output
        assert "yolo" in result.output
        assert "db" in result.output
        assert "generate" in result.output

    def test_ocr_help(self):
        result = runner.invoke(app, ["ocr", "--help"])
        assert result.exit_code == 0
        assert "detect" in result.output
        assert "engines" in result.output

    def test_yolo_help(self):
        result = runner.invoke(app, ["yolo", "--help"])
        assert result.exit_code == 0
        assert "predict" in result.output
        assert "train" in result.output

    def test_db_help(self):
        result = runner.invoke(app, ["db", "--help"])
        assert result.exit_code == 0
        assert "connect" in result.output
        assert "backends" in result.output

    def test_db_backends(self):
        result = runner.invoke(app, ["db", "backends"])
        assert result.exit_code == 0
        assert "postgresql" in result.output

    def test_generate_help(self):
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "fullstack" in result.output

    def test_ocr_detect_missing_image(self):
        result = runner.invoke(app, ["ocr", "detect", "/nonexistent.png"])
        assert result.exit_code == 1


class TestGenerators:
    """Unit tests for generators directly (fullstack is interactive, tested via generators)."""

    def test_backend_fastapi(self, tmp_path):
        from aiops.generators.backend import BackendGenerator

        gen = BackendGenerator("fastapi")
        path = gen.generate("test_api", output_dir=tmp_path, with_docker=False, with_auth=False)
        assert (path / "app" / "main.py").exists()
        assert (path / "requirements.txt").exists()

    def test_backend_flask(self, tmp_path):
        from aiops.generators.backend import BackendGenerator

        gen = BackendGenerator("flask")
        path = gen.generate("test_flask", output_dir=tmp_path, with_docker=False, with_auth=False)
        assert (path / "app" / "__init__.py").exists()
        assert (path / "run.py").exists()

    def test_frontend_scaffold(self, tmp_path):
        from aiops.generators.frontend import FrontendGenerator

        gen = FrontendGenerator()
        path = gen.generate("test_ui", output_dir=tmp_path)
        assert (path / "src" / "lib" / "api.ts").exists()
        assert (path / "src" / "components" / "Layout.tsx").exists()

    def test_frontend_addons(self, tmp_path):
        import json
        from aiops.generators.frontend import FrontendGenerator
        from aiops.cli.generate_cmd import _apply_frontend_addons

        gen = FrontendGenerator()
        path = gen.generate("test_addons", output_dir=tmp_path)
        _apply_frontend_addons(path, ["Tailwind CSS", "React Router", "shadcn/ui"])

        pkg = json.loads((path / "package.json").read_text())
        assert "tailwindcss" in pkg.get("devDependencies", {})
        assert "react-router" in pkg.get("dependencies", {})
        assert "clsx" in pkg.get("dependencies", {})
        assert (path / "src" / "router.tsx").exists()
        assert (path / "src" / "lib" / "utils.ts").exists()
        assert (path / "src" / "components" / "ui" / "button.tsx").exists()
