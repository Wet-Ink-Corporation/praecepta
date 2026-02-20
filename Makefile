.PHONY: test test-unit test-int lint format typecheck boundaries verify install docs docs-dev changelog changelog-preview bump-patch bump-minor bump-major help

test:           ## Run all tests
	uv run pytest

test-unit:      ## Run unit tests only
	uv run pytest -m unit

test-int:       ## Run integration tests only
	uv run pytest -m integration

lint:           ## Auto-fix lint issues and format code
	uv run ruff check packages/ tests/ examples/ --fix
	uv run ruff format packages/ tests/ examples/

format:         ## Format code with ruff
	uv run ruff format packages/ tests/ examples/

typecheck:      ## Run mypy strict type checking
	uv run mypy

boundaries:     ## Check architecture import boundaries
	uv run lint-imports

verify:         ## Full verification (lint + format + typecheck + boundaries + test)
	uv run ruff check packages/ tests/ examples/ --fix
	uv run ruff format packages/ tests/ examples/
	uv run mypy
	uv run lint-imports
	uv run pytest

install:        ## Install all dependencies and git hooks
	uv sync --dev
	uv run pre-commit install --hook-type commit-msg

# ── Docs ──────────────────────────────────────────────────────────────

docs:           ## Build documentation site (MkDocs + shadcn)
	uv run mkdocs build -f docs/mkdocs.yml

docs-dev:       ## Start docs dev server
	uv run mkdocs serve -f docs/mkdocs.yml

# ── Release & Changelog ──────────────────────────────────────────────

changelog:          ## Generate CHANGELOG.md from full git history
	uv run cz changelog

changelog-preview:  ## Preview unreleased changes (dry run)
	uv run cz changelog --dry-run --unreleased-version "Unreleased"

bump-patch:         ## Bump patch version (e.g., 0.3.0 -> 0.3.1)
	uv run cz bump --patch --changelog

bump-minor:         ## Bump minor version (e.g., 0.3.0 -> 0.4.0)
	uv run cz bump --minor --changelog

bump-major:         ## Bump major version (e.g., 0.3.0 -> 1.0.0)
	uv run cz bump --major --changelog

# ── Help ─────────────────────────────────────────────────────────────

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
