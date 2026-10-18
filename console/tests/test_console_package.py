"""What card 002 changed and what it must not have: the store's default root, and the log names.

The store's default root is the repository the package sits in, found by walking up to the
first folder that holds both `contracts/` and `console/`. When there is none, it refuses; a
guessed path is never returned. And a rename must not move the names the daily log hangs on.
"""

import ast
from pathlib import Path

import pytest

from sma_console.agents import sma_files
from sma_console.agents.sma_files import ROOT_ENV, RootNotFoundError, repository_root
from sma_console.auth import applog
from sma_console.server.__main__ import agent_store_of, parse_args

PKG = Path(__file__).resolve().parents[1] / "src" / "sma_console"


def _repo(folder: Path, *, contracts=True, console=True) -> Path:
    folder.mkdir(parents=True)
    if contracts:
        (folder / "contracts").mkdir()
    if console:
        (folder / "console").mkdir()
    return folder


def test_the_root_is_the_folder_above_that_holds_contracts_and_console(tmp_path):
    repo = _repo(tmp_path / "repo")
    assert repository_root(repo / "console" / "src" / "pkg" / "x.py") == repo.resolve()


def test_the_nearest_such_folder_wins(tmp_path):
    outer = _repo(tmp_path / "outer")
    inner = _repo(outer / "inner")
    assert repository_root(inner / "console" / "x.py") == inner.resolve()


@pytest.mark.parametrize("has", [{"contracts": True, "console": False},
                                 {"contracts": False, "console": True},
                                 {"contracts": False, "console": False}])
def test_a_folder_with_only_one_of_the_two_is_not_a_repository(tmp_path, has):
    lone = _repo(tmp_path / "lone", **has)
    with pytest.raises(RootNotFoundError) as e:
        repository_root(lone / "src" / "x.py")
    assert "contracts/ and console/" in str(e.value) and ROOT_ENV in str(e.value)


def test_the_real_default_is_this_repository():
    assert (repository_root() / "contracts").is_dir() and (repository_root() / "console").is_dir()
    assert PKG.is_relative_to(repository_root())


def test_a_store_started_with_no_root_stops_with_the_reason(monkeypatch):
    monkeypatch.delenv(ROOT_ENV, raising=False)

    def nowhere(start=None):
        raise RootNotFoundError("no repository above here: nowhere")

    monkeypatch.setattr(sma_files, "repository_root", nowhere)
    with pytest.raises(SystemExit) as e:
        agent_store_of(parse_args(["--store", "sma"]))
    assert "--store sma" in str(e.value) and "nowhere" in str(e.value)


def test_a_given_root_is_used_as_given_even_when_no_repository_is_found(monkeypatch, tmp_path):
    monkeypatch.setattr(sma_files, "repository_root", lambda start=None: pytest.fail("walked"))
    assert sma_files.SmaFiles(tmp_path).root == tmp_path


def test_every_module_logger_stays_under_the_daily_log_logger():
    """`getLogger(__name__)` would follow the package name and drop out of the daily log."""
    stray = []
    for path in sorted(PKG.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "getLogger"
                    and node.args):
                arg = node.args[0]
                ok = (isinstance(arg, ast.Name) and arg.id == "LOGGER_NAME"
                      or isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                      and (arg.value == applog.LOGGER_NAME
                           or arg.value.startswith(applog.LOGGER_NAME + ".")))
                if not ok:
                    stray.append(f"{path.relative_to(PKG).as_posix()}:{node.lineno}")
    assert not stray, stray
