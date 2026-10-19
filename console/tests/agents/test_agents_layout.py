"""The one rule for where the microscope's run-side folders are (console card 005, plan.md 15).

Each of `runs` and `approvals` is read from `microscope_runtime/<folder>/` when that folder exists,
else from `microscope_agent/<folder>/`, each decided on its own, and never both. The simulation
seat keeps `simulation_agent/`.
"""

from __future__ import annotations

import pytest

from sma_console.agents import RunsFolderNotFoundError, SmaFiles
from sma_console.agents.layout import RUN_SIDE_FOLDERS, RUNTIME_FOLDER, run_side_folder


def make(root, *places: str):
    for place in places:
        (root / place).mkdir(parents=True)
    return root


@pytest.mark.parametrize("folder", RUN_SIDE_FOLDERS)
def test_a_folder_in_the_runtime_place_is_read_from_there(tmp_path, folder):
    root = make(tmp_path, f"{RUNTIME_FOLDER}/{folder}")
    assert run_side_folder(root, "microscope", folder) == root / RUNTIME_FOLDER / folder


@pytest.mark.parametrize("folder", RUN_SIDE_FOLDERS)
def test_a_tree_from_before_the_move_is_read_from_the_agent_folder(tmp_path, folder):
    root = make(tmp_path, f"microscope_agent/{folder}")
    assert run_side_folder(root, "microscope", folder) == root / "microscope_agent" / folder


@pytest.mark.parametrize("folder", RUN_SIDE_FOLDERS)
def test_when_both_exist_one_is_read_and_it_is_the_runtime_one(tmp_path, folder):
    root = make(tmp_path, f"{RUNTIME_FOLDER}/{folder}", f"microscope_agent/{folder}")
    assert run_side_folder(root, "microscope", folder) == root / RUNTIME_FOLDER / folder


@pytest.mark.parametrize("folder", RUN_SIDE_FOLDERS)
def test_a_folder_in_neither_place_is_none_and_not_a_guessed_path(tmp_path, folder):
    root = make(tmp_path, "microscope_agent", RUNTIME_FOLDER)  # the seats' folders, not these
    assert run_side_folder(root, "microscope", folder) is None


def test_each_folder_is_decided_on_its_own(tmp_path):
    """Runs moved and approvals not yet, the time between the two steps."""
    root = make(tmp_path, f"{RUNTIME_FOLDER}/runs", "microscope_agent/approvals")
    assert run_side_folder(root, "microscope", "runs") == root / RUNTIME_FOLDER / "runs"
    assert run_side_folder(root, "microscope", "approvals") == root / "microscope_agent" / "approvals"
    # and the other way round: the folder that has not moved stays where it is
    other = make(tmp_path / "other", f"{RUNTIME_FOLDER}/approvals", "microscope_agent/runs")
    assert run_side_folder(other, "microscope", "approvals") == other / RUNTIME_FOLDER / "approvals"
    assert run_side_folder(other, "microscope", "runs") == other / "microscope_agent" / "runs"


@pytest.mark.parametrize("folder", RUN_SIDE_FOLDERS)
def test_the_simulation_seat_keeps_its_own_folder(tmp_path, folder):
    root = make(tmp_path, f"{RUNTIME_FOLDER}/{folder}", f"simulation_agent/{folder}")
    assert run_side_folder(root, "simulation", folder) == root / "simulation_agent" / folder
    bare = make(tmp_path / "bare", f"{RUNTIME_FOLDER}/{folder}")
    assert run_side_folder(bare, "simulation", folder) is None  # never the microscope's


def test_only_runs_and_approvals_move(tmp_path):
    with pytest.raises(ValueError):
        run_side_folder(tmp_path, "microscope", "questions")  # the questions stay in microscope_agent/


def test_the_store_says_the_runs_cannot_be_seen_and_not_that_there_are_none(tmp_path):
    root = make(tmp_path, "microscope_agent/questions", "simulation_agent/runs")
    store = SmaFiles(root)
    for call in (lambda: store.list_runs("microscope"), store.running_microscope_runs,
                 lambda: store.get_run("microscope", "run-20261005-001"),
                 lambda: store.run_stream("microscope", "run-20261005-001")):
        with pytest.raises(RunsFolderNotFoundError) as e:
            call()
        assert "not found" in str(e.value) and "not the same as there being none" in str(e.value)
    assert store.list_runs("simulation") == []  # the simulation seat keeps "no folder, no runs"
    make(root, "microscope_runtime/runs")  # a folder that exists and is empty IS "no runs"
    assert store.list_runs("microscope") == [] and store.running_microscope_runs() == []


def test_the_store_reads_runs_and_approvals_each_from_its_own_place(tmp_path):
    root = make(tmp_path, f"{RUNTIME_FOLDER}/runs/run-20261005-001", "microscope_agent/approvals")
    (root / RUNTIME_FOLDER / "runs" / "run-20261005-001" / "log.json").write_text("{}", "utf-8")
    store = SmaFiles(root)
    assert [r.run_id for r in store.list_runs("microscope")] == ["run-20261005-001"]
    assert store.list_approvals("microscope") == []  # the folder is there, with nothing in it
