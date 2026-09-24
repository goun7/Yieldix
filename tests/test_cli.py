"""
Tests for Yieldix CLI commands via Click CliRunner.
"""

import pytest
from click.testing import CliRunner

from yieldix.cli.main import main


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "16.0.0" in result.output


def test_cli_status():
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--tenant", "cust_cli_test"])
    assert result.exit_code == 0
    assert "YIELDIX ENGINE STATUS" in result.output
    assert "c1_receptionist" in result.output


def test_cli_ingest():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ingest", "--tenant", "cust_cli_test", "--name", "Ali Vural", "--phone", "+905551234567"],
    )
    assert result.exit_code == 0
    assert "call_dispatched" in result.output
    assert "Ali Vural" in result.output or "CALL_CONNECTED_AND_BOOKED" in result.output


def test_cli_simulate():
    import random
    random.seed(42)
    runner = CliRunner()
    result = runner.invoke(main, ["simulate", "--runs", "10000", "--retainer", "2500"])
    assert result.exit_code == 0
    assert "SIMULATION RESULTS" in result.output
    assert "P50 (Median)" in result.output


def test_cli_report():
    runner = CliRunner()
    result = runner.invoke(main, ["report", "--tenant", "cust_cli_test"])
    assert result.exit_code == 0
    assert "YIELDIX AYLIK İMZALI PERFORMANS RAPORU" in result.output


def test_cli_serve_help():
    runner = CliRunner()
    result = runner.invoke(main, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output


def test_cli_serve_no_block():
    runner = CliRunner()
    result = runner.invoke(main, ["serve", "--port", "8995", "--no-block"])
    assert result.exit_code == 0
    assert "Starting Yieldix Cockpit on http://127.0.0.1:8995" in result.output


def test_cli_entrypoint_main():
    import runpy
    import sys
    saved_argv = sys.argv
    try:
        sys.argv = ["yieldix", "--version"]
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("yieldix.cli.main", run_name="__main__", alter_sys=True)
        assert exc.value.code == 0
    finally:
        sys.argv = saved_argv


