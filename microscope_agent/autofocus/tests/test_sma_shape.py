"""`microscope_agent/` already has the shape soft-matter-agents will check when it is copied
there (docs/integration-sma.md section 9; that repository's contracts/validate.py checks 13,
16 and 82 at ``SMA_SHAPE_COMMIT``): flat src (or src/devices/<file>), flat tests, stdlib +
numpy imports only, no relative or dino_autofocus imports, no device importing a sibling,
and (D-03) no dino path in any text under microscope_agent/: the files must read the same
after the copy, where ``scripts/`` and ``docs/`` would mean that repository's folders.

D-03 also gives every flat file an origin header (``dino_autofocus.flat_origin``): the commit
that holds this body, as a public URL, and the body's SHA-256. The tests at the end check the
header against the body, the named commit against the body (via git), and -- when a
soft-matter-agents checkout is beside this repository or at ``DINO_AF_SMA_ROOT`` -- that the
pin is in its history, that the checks the mirror follows still exist, and that no file that
exists on both sides has drifted."""

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dino_autofocus import flat_origin

ROOT = Path(__file__).resolve().parents[1] / "microscope_agent"
REPO = ROOT.parent
ALLOWED_THIRD_PARTY = {"numpy"}  # what the soft-matter-agents `mic` environment has
# The soft-matter-agents commit whose validate.py checks the mirror's shape follows. Re-pin
# it (and re-read checks 13, 16 and 82) when the drift test below says the checkout moved.
SMA_SHAPE_COMMIT = "b346c02d5de14e23a3036b92e0245b8b68c0fd6d"
# Tokens that mean something else once the files sit in soft-matter-agents (D-03): the dino
# package name and dino's own folders. Prose names the thing ("the engine's guards", "the 4x
# scan script") instead; the origin header names the commit.
FORBIDDEN_TOKENS = ("dino_autofocus", "scripts/", "docs/")
SKIP = {"__pycache__"}


def _files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and not SKIP & set(p.parts))


def _imports(path: Path) -> list[tuple[str, int]]:
    """(top-level module, relative level) of every import, inside functions too."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(a.name.split(".")[0], 0) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            out.append(((node.module or "").split(".")[0], node.level))
    return out


def test_src_is_flat_or_devices():
    bad = []
    for p in _files(ROOT / "src"):
        rel = p.relative_to(ROOT / "src").parts
        ok = (len(rel) == 1 or (len(rel) == 2 and rel[0] == "devices")) and p.suffix == ".py"
        if not ok or p.name == "__init__.py":
            bad.append(str(p))
    assert not bad, bad
    assert list((ROOT / "src").glob("*.py")), "nothing to check"


def test_tests_are_flat_py_files():
    bad = [str(p) for p in _files(ROOT / "tests")
           if len(p.relative_to(ROOT / "tests").parts) != 1 or p.suffix != ".py"]
    assert not bad, bad


def test_imports_are_stdlib_or_numpy_and_never_relative():
    allowed = set(sys.stdlib_module_names) | ALLOWED_THIRD_PARTY | {"__future__"}
    bad = []
    for p in [*_files(ROOT / "src"), *_files(ROOT / "tests")]:
        for mod, level in _imports(p):
            if level or mod not in allowed:
                bad.append(f"{p.name}: {'.' * level}{mod}")
    assert not bad, bad


# D-02: every bench measurement and tuning default left the flat files for
# src/dino_autofocus/bench_values.py. What may still be written as a number there is listed
# per file; anything else fails. Categories: structure (bit depths, bin sizes, a count
# ceiling, minimum point counts), unit conversions (1000 um/mm, 500 um per mm of diameter),
# statistics definitions (99.9th percentile, 1.4826 MAD factor, 256 histogram bins),
# epsilons, and a few detection tuning defaults in the held-back map_* files that OD-29
# keeps in dino until a soft-matter-agents place exists (they are tuning, not bench facts).
ALWAYS_OK = {0, 1, -1, 2, 0.5, 100, 255}
ALLOWED_LITERALS: dict[str, set[float]] = {
    # bit-depth range of a uint16 frame, block minimum size, 99.9th percentile, epsilons;
    # no clip level, bin size or block grid since D-03c
    "focus_classical.py": {16, 3, 99.9, 1e-06, 1e-12, 1e-30},
    "focus_run_log.py": set(),
    "focus_search.py": {4, 1e-06, 1e-09},  # rounding digits, epsilons (no count since D-03f)
    "focus_step_rules.py": {1e-06},  # one float epsilon; every limit is an argument
    "focus_verdict.py": {1e-12},
    "focus_verdict_model.py": set(),  # the model-reading verdict, out of the first copy
    "map_edge.py": {8.0, 150, 3, 1.4826, 5, 36, 30, 6, 256, 1e-12, 1e-06, 1e-09, 0.001, 4,
                    0.03, 1000},
    # loop arc; coverslip and sample-size form defaults (lab values, candidates for cards)
    "map_geometry.py": {330.0, 170.0, 24.0, 50.0},
    "map_mosaic.py": {8, 4.0, 16, 1.5, 25.0, 6.0, 0.3, 500, 10.0, 1.4826, 3},
    "map_tiles.py": {500, 3, 1000},
}


def _number_literals(path: Path) -> set[float]:
    out: set[float] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            out.add(node.value)
    return out


def test_no_bench_or_tuning_number_is_written_in_a_flat_file():
    files = {p.name: p for p in _files(ROOT / "src") if p.suffix == ".py"}
    assert set(files) == set(ALLOWED_LITERALS), "a new flat file needs its own allow-list row"
    bad = {name: sorted(_number_literals(p) - ALLOWED_LITERALS[name] - ALWAYS_OK, key=float)
           for name, p in files.items()}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, f"numbers that must come from the caller (bench_values): {bad}"


def test_flat_files_name_no_dino_constant():
    """The removed names must not creep back under their old spelling."""
    gone = ("DEFAULT_CENTRE_UM", "PARFOCAL_4X_TO_100X_UM", "DARK_OFFSET_ADU", "SIGNAL_MIN_ADU",
            "DEFAULT_EXPOSURE_MS", "MIN_DYNAMIC_RANGE_ADU", "MIN_CURVE_CONTRAST",
            "MIN_SWEEP_FRAMES", "IN_FOCUS_DOF", "MAX_SIGMA_DOF", "MAX_SATURATED_FRACTION",
            "DROPOUT_TOLERANCE", "DOUBLE_PEAK_PROMINENCE", "DEFAULT_UM_PER_PX",
            "DEFAULT_M_PX_PER_UM", "BENCH_M_4X")
    for p in _files(ROOT / "src"):
        text = p.read_text(encoding="utf-8")
        hits = [g for g in gone if re.search(rf"^{g}\\s*=", text, re.M)]
        assert not hits, f"{p.name} defines {hits}"


def test_no_dino_path_token_under_microscope_agent():
    hits = []
    for p in _files(ROOT):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            hits += [f"{p.relative_to(ROOT).as_posix()}:{i}: {tok}" for tok in FORBIDDEN_TOKENS
                     if tok in line]
    assert not hits, hits


def test_no_file_shadows_a_stdlib_module():
    stems = {p.stem for p in _files(ROOT / "src")}
    assert not stems & set(sys.stdlib_module_names)


def test_devices_import_no_sibling():
    siblings = {p.stem for p in _files(ROOT / "src")}
    bad = [f"{p.name}: {m}" for p in _files(ROOT / "src" / "devices")
           for m, _ in _imports(p) if m in siblings]
    assert not bad, bad


# D-03: origin headers. A body edit without a new header fails here; so does a header that
# names a commit whose file has a different body.

def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess | None:
    if shutil.which("git") is None:
        return None
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True)


def test_every_flat_file_has_an_origin_header_naming_its_body():
    assert flat_origin.flat_files(REPO), "nothing to check"
    assert not flat_origin.check(REPO), flat_origin.check(REPO)


def test_the_named_commit_holds_this_body():
    """The header's URL resolves to a file with exactly this body."""
    shallow = _git("rev-parse", "--is-shallow-repository", cwd=REPO)
    if shallow is None or shallow.returncode or shallow.stdout.strip() == b"true":
        pytest.skip("no git or a shallow clone: the named commit cannot be read")
    problems = []
    for p in flat_origin.flat_files(REPO):
        header, body = flat_origin.split(p.read_text(encoding="utf-8"))
        if header is None or header.origin != flat_origin.ORIGIN:
            continue  # no header: reported above; a mirror: checked against SMA below
        shown = _git("show", f"{header.commit}:{header.path}", cwd=REPO)
        if shown.returncode:
            problems.append(f"{header.path}: commit {header.commit[:12]} is not in this"
                            f" repository or has no such file")
            continue
        _, named = flat_origin.split(shown.stdout.decode("utf-8"))
        if flat_origin.body_sha256(named) != flat_origin.body_sha256(body):
            problems.append(f"{header.path}: the body at {header.commit[:12]} differs; name"
                            f" the commit that holds this body")
    assert not problems, problems


def _sma_root() -> Path | None:
    env = os.environ.get("DINO_AF_SMA_ROOT")
    candidates = ([Path(env)] if env else
                  [REPO.parent / "soft-matter-agents", REPO.parents[1] / "soft-matter-agents"])
    return next((c for c in candidates if (c / "contracts" / "validate.py").is_file()), None)


SMA_CHECKS_FOLLOWED = ("check_13_paths", "check_16_dependency_direction",
                       "check_82_imports_are_declared")


def test_soft_matter_agents_checkout_has_the_pin_and_no_drift():
    """Read-only look at the soft-matter-agents checkout, when there is one."""
    sma = _sma_root()
    if sma is None:
        pytest.skip("no soft-matter-agents checkout beside this repository (DINO_AF_SMA_ROOT)")
    problems = []
    anc = _git("merge-base", "--is-ancestor", SMA_SHAPE_COMMIT, "HEAD", cwd=sma)
    if anc is not None and anc.returncode:
        problems.append(f"SMA_SHAPE_COMMIT {SMA_SHAPE_COMMIT[:12]} is not in the checkout's"
                        f" history: re-pin and re-read the checks")
    validate = (sma / "contracts" / "validate.py").read_text(encoding="utf-8")
    problems += [f"validate.py no longer defines {name}" for name in SMA_CHECKS_FOLLOWED
                 if f"def {name}(" not in validate]
    for p in flat_origin.flat_files(REPO):
        rel = p.relative_to(REPO)
        theirs = sma / rel
        if not theirs.is_file():
            continue  # not copied yet (or held back): nothing to compare
        _, ours = flat_origin.split(p.read_text(encoding="utf-8"))
        _, there = flat_origin.split(theirs.read_text(encoding="utf-8"))
        if flat_origin.body_sha256(ours) != flat_origin.body_sha256(there):
            problems.append(f"{rel.as_posix()}: body differs from the soft-matter-agents copy"
                            f" (drift: mirror the change back or forward, by card)")
    # D-06: every mirrored file's body is the one at SMA_MIRROR_COMMIT in soft-matter-agents
    for rel in sorted(flat_origin.MIRRORED):
        shown = _git("show", f"{flat_origin.SMA_MIRROR_COMMIT}:{rel}", cwd=sma)
        if shown is None:
            break
        if shown.returncode:
            problems.append(f"{rel}: SMA_MIRROR_COMMIT has no such file in the checkout")
            continue
        _, there = flat_origin.split(shown.stdout.decode("utf-8"))
        _, ours = flat_origin.split((REPO / rel).read_text(encoding="utf-8"))
        if flat_origin.body_sha256(ours) != flat_origin.body_sha256(there):
            problems.append(f"{rel}: the mirror differs from soft-matter-agents at "
                            f"{flat_origin.SMA_MIRROR_COMMIT[:12]}")
    assert not problems, problems
