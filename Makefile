.PHONY: install test build publish clean lint format check help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install package with dev dependencies
	uv venv --python 3.12
	uv pip install -e ".[dev]"

install-all: ## Install package with all optional dependencies
	uv venv --python 3.12
	uv pip install -e ".[all,dev]"

test: ## Run tests
	uv run pytest tests/ -v

test-cov: ## Run tests with coverage
	uv run pytest tests/ -v --cov=aiops --cov-report=term-missing

lint: ## Run linter
	uv run ruff check src/ tests/

format: ## Format code
	uv run ruff format src/ tests/

check: lint test ## Run linter + tests

build: ## Build distribution packages
	uv build

publish: build ## Publish to PyPI
	uv publish

clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov/
