.PHONY: test test-unit test-int lint format typecheck boundaries verify install help

test:           ## Run all tests
	uv run pytest

test-unit:      ## Run unit tests only
	uv run pytest -m unit

test-int:       ## Run integration tests only
	uv run pytest -m integration

lint:           ## Run ruff linter with auto-fix
	uv run ruff check packages/ tests/ examples/ --fix

format:         ## Format code with ruff
	uv run ruff format packages/ tests/ examples/

typecheck:      ## Run mypy strict type checking
	uv run mypy

boundaries:     ## Check architecture import boundaries
	uv run lint-imports

verify:         ## Full verification (lint + typecheck + boundaries + test)
	uv run ruff check packages/ tests/ examples/
	uv run mypy
	uv run lint-imports
	uv run pytest

install:        ## Install all dependencies
	uv sync --dev

# ── Help ─────────────────────────────────────────────────────────────

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
