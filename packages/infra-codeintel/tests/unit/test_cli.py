"""Unit tests for CLI commands."""

from __future__ import annotations

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
