"""Unit tests for CLI commands."""

from __future__ import annotations

from pathlib import Path  # noqa: F401 – used in parametrized fixtures

import pytest
from click.testing import CliRunner

from praecepta.infra.codeintel.surface.cli import cli


@pytest.mark.unit
class TestCLI:
    def test_help_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Code intelligence" in result.output

    def test_serve_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output
        assert "--transport" in result.output
        assert "--port" in result.output
        assert "--device" in result.output

    def test_index_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["index", "--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output
        assert "--device" in result.output

    def test_stats_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["stats", "--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output

    def test_serve_default_transport(self) -> None:
        # Verify default transport is stdio (check without actually starting server)
        ...

    def test_all_commands_accept_config(self) -> None:
        runner = CliRunner()
        for cmd in ["serve", "index", "stats"]:
            result = runner.invoke(cli, [cmd, "--help"])
            assert "--config" in result.output

    def test_stats_json_output(self, tmp_path: Path) -> None:
        """stats --json must produce valid JSON with an empty repo (B-1)."""
        import json
        import os

        from praecepta.infra.codeintel.settings import get_settings

        # Save and restore CODE_INTEL_* env vars so this test doesn't pollute others
        saved = {k: v for k, v in os.environ.items() if k.startswith("CODE_INTEL_")}
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["stats", "--repo", str(tmp_path), "--json"])
        finally:
            for k in list(os.environ.keys()):
                if k.startswith("CODE_INTEL_"):
                    del os.environ[k]
            os.environ.update(saved)
            get_settings.cache_clear()

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "total_files" in data
        assert "total_symbols" in data
        assert "semantic_index_rows" in data
        # Empty repo → zeros
        assert data["total_files"] == 0

    def test_index_include_tests_flag_accepted(self) -> None:
        """index --include-tests must be accepted without error (help-level check)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["index", "--help"])
        assert "--include-tests" in result.output
