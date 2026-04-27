import pytest
from click.testing import CliRunner
from nexus.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_status(runner, monkeypatch, tmp_path):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "nexus" in result.output.lower()


def test_cli_forget(runner, monkeypatch, tmp_path):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "nexus.db"
    db_path.touch()
    result = runner.invoke(main, ["forget", "--yes"])
    assert result.exit_code == 0
