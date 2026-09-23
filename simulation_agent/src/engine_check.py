"""Is the engine here, and which build is it -- the first thing to run on a new machine.

    python3 -m src.engine_check          # from simulation_agent/
    python3 -m src.engine_check --json

HOOMD-blue is not on PyPI (plan.md 7, 2026-09-22), so a PyPI-shaped
dependency list cannot name it. What names it, as of 2026-09-23, is the pixi
table in `pyproject.toml` -- `[tool.pixi.feature.sim.dependencies]` -- with
`pixi.lock` fixing the exact build per platform, so one interpreter
(`pixi install -e sim`) runs the validator, the mock and the engine. This
module reads that pin -- spec from the table, build from the lock for this
platform -- and compares it with what the interpreter running it can import.
`src/environment.yml` was the bridge before pixi (85acb62..af1276d) and was
deleted when the pixi environment installed and ran the validator (019).

The exit status is the answer, for scripts; the text is for people.

    0   the engine imports and is the pinned build
    2   the engine does not import; the install lines are printed
    3   the engine imports and is NOT the pinned build. A run would still
        go, and would record the build it actually got (engine_build); this
        says so before any run does.

It refuses nothing and decides nothing. A run on a different build is
allowed and RECORDED, which is the operator's arrangement (4.6.5); this is
the same fact reported before a run instead of inside one. Nothing here
reads the store and nothing here is a fact about the world: it is a
measurement of this interpreter, and it lands on no card.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import platform
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYPROJECT = REPO / "pyproject.toml"
PIXI_LOCK = REPO / "pixi.lock"
# conda-forge builds hoomd 7.2.0 for these and no others. win-64 was tried
# and fails to solve (plan.md 7, 2026-09-22). Overridden by the pixi table's
# `sim` feature platforms when that table exists -- read, not repeated.
PLATFORMS = ("linux-64", "osx-64", "osx-arm64")

# THE DECLARATION OF RECORD IS pyproject.toml's [tool.pixi.*] (architecture,
# 2026-09-23): the spec is `feature.sim.dependencies.hoomd`, and the exact
# build per platform is the `hoomd-<version>-<build>.conda` line pixi.lock
# holds for that platform. No fallback: a repository without the table has
# no engine declaration, and saying so is the honest report.
LOCKED = re.compile(r"conda-forge/(?P<subdir>[a-z0-9-]+)/hoomd-(?P<version>[0-9][^-]*)-(?P<build>[^\s/]+)\.conda")

def read_pin() -> dict:
    """The pin of record: {version, build, line, file, spec, source}.

    `spec` is what pyproject.toml's pixi table asks (e.g. `>=7.2`), and
    version/build are what pixi.lock resolved for THIS platform, which is the
    number an installed engine is compared against. A platform the `sim`
    feature excludes (win-64) gets the spec and no locked build.
    """
    if PYPROJECT.exists():
        import tomllib                                 # noqa: PLC0415
        with PYPROJECT.open("rb") as fh:
            pixi = tomllib.load(fh).get("tool", {}).get("pixi")
        if pixi and "hoomd" in pixi.get("feature", {}).get("sim", {}).get("dependencies", {}):
            sim = pixi["feature"]["sim"]
            spec = sim["dependencies"]["hoomd"]
            global PLATFORMS
            PLATFORMS = tuple(sim.get("platforms") or PLATFORMS)
            locked = None
            if PIXI_LOCK.exists():
                sub = conda_subdir()
                for m in LOCKED.finditer(PIXI_LOCK.read_text()):
                    if m.group("subdir") == sub:
                        locked = m.groupdict()
                        break
            return {
                "version": locked["version"] if locked else None,
                "build": locked["build"] if locked else None,
                "spec": spec,
                "line": f"hoomd{spec} (pixi.lock: {locked['version']}-{locked['build']})" if locked
                        else f"hoomd{spec} (no locked build for {conda_subdir()})",
                "file": "pyproject.toml [tool.pixi.feature.sim] + pixi.lock",
                "source": "pixi",
            }
    raise LookupError(f"{PYPROJECT} has no [tool.pixi.feature.sim.dependencies].hoomd; the engine is undeclared")


def conda_subdir() -> str:
    """conda's name for this platform, derived from what Python reports."""
    system, machine = platform.system(), platform.machine().lower()
    if system == "Windows":
        return "win-64"
    if system == "Darwin":
        return "osx-arm64" if machine in ("arm64", "aarch64") else "osx-64"
    if system == "Linux":
        return "linux-64" if machine in ("x86_64", "amd64") else f"linux-{machine}"
    return f"{system.lower()}-{machine}"


def instruction(pin: dict | None = None) -> str:
    """The text a mock-only run emits, naming the platform it is on (4.6.5, amended 2026-09-22).

    A reduced path is legitimate and never silent: finding no engine, the
    operator runs the mock and says so, the way `degraded` carries the
    librarian's name. The text changes no verdict. win-64 has no HOOMD build
    at all, so Windows gets its own route -- the engine lives in WSL2, which
    is linux-64 (plan.md 7) -- and the other platforms get the pixi lines.
    """
    pin = pin or read_pin()
    sub = conda_subdir()
    head = f"mock_backend ran because hoomd is not importable in this interpreter on {sub}."
    if sub == "win-64":
        return (head + " conda-forge builds no HOOMD for win-64, under any packaging tool. The engine's "
                "route on this machine is WSL2 (linux-64): inside it, from the repository root:\n    "
                + "\n    ".join(install_lines(pin)))
    if sub not in PLATFORMS:
        return (head + f" conda-forge builds HOOMD 7.2.0 for {', '.join(PLATFORMS)} only; {sub} needs a "
                "source build (cmake -B build -S . -GNinja; ninja; ninja install).")
    return head + " From the repository root:\n    " + "\n    ".join(install_lines(pin))


def install_lines(pin: dict) -> list[str]:
    """What to type, from the repository root. One place, quoted by the backend too."""
    # Both lines run from any directory inside the repository: pixi finds the
    # manifest by walking up, and the `cd` names where `src` resolves. A
    # command inside an error message that does not run where the error
    # appeared is worth nothing (manager, 2026-09-23).
    return [
        f"pixi install -e sim                                       # pixi.lock decides every build",
        f"cd {REPO}/simulation_agent && pixi run -e sim python -m src.engine_check",
    ]


def check(pin: dict) -> dict:
    """Measure this interpreter against the pin. Pure report, no side effects."""
    out = {
        "pin": pin,
        "interpreter": sys.executable,
        "python": sys.version.split()[0],
        "platform": f"{platform.system()}-{platform.machine()}",
        "importable": False,
        "build": None,
        "matches_pin": None,
        "variant_checked": False,
        "gsd": None,
    }
    try:
        import hoomd                                   # noqa: PLC0415
    except ImportError as exc:
        out["import_error"] = str(exc)
        return out
    from . import hoomd_backend                        # noqa: PLC0415  (after the import: no engine, no need)
    out["importable"] = True
    build = hoomd_backend.engine_build(hoomd)
    out["build"] = build
    ok = build["version"] == pin["version"] if pin["version"] else False
    if pin.get("source") == "pixi" and pin["build"] and build.get("conda_package"):
        # pixi.lock names the exact artefact; the installed one either is it or is not.
        out["variant_checked"] = True
        out["matches_pin"] = ok and build["conda_package"].get("build") == pin["build"]
        try:
            import gsd.version                         # noqa: PLC0415
            out["gsd"] = gsd.version.version
        except ImportError:
            out["gsd"] = None
        return out
    # The variant (*cpu* / *gpu*) is a property of the conda build string,
    # which a source build has none of. Then the version is all that can be
    # compared, and the record says the variant went unchecked rather than
    # calling it matched.
    if pin["build"] and build.get("conda_package") and build["conda_package"].get("build"):
        out["variant_checked"] = True
        ok = ok and fnmatch.fnmatchcase(build["conda_package"]["build"], pin["build"])
    out["matches_pin"] = ok
    try:
        import gsd.version                             # noqa: PLC0415
        out["gsd"] = gsd.version.version
    except ImportError:
        out["gsd"] = None
    return out


def status(report: dict) -> int:
    if not report["importable"]:
        return 2
    return 0 if report["matches_pin"] else 3


def render(report: dict) -> str:
    pin = report["pin"]
    lines = [
        f"engine_check  {pin['file']} pins {pin['line'].lstrip('- ').strip()}",
        f"interpreter   {report['interpreter']}  ({report['python']}, {report['platform']})",
    ]
    if not report["importable"]:
        lines.append(f"hoomd         not importable ({report.get('import_error')})")
        lines.append(
            "verdict       MISSING. HOOMD-blue is not on PyPI; it ships through conda-forge for "
            + ", ".join(PLATFORMS) + " and not win-64. From anywhere inside the repository:"
        )
        lines += [f"    {l}" for l in install_lines(pin)]
        lines.append("The pipeline runs without it: hand the operator mock_backend explicitly (4.6.5).")
        return "\n".join(lines)
    b = report["build"]
    pkg = b.get("conda_package") or {}
    where = (f"{pkg.get('build')}  {str(pkg.get('channel', '')).rsplit('/', 1)[-1]}/{pkg.get('subdir')}"
             if pkg else "not a conda package (source build?)")
    lines.append(
        f"hoomd         {b['version']}  {where}  gpu={b['gpu_enabled']} mpi={b['mpi_enabled']}  {b['compile_flags']}"
    )
    lines.append(f"gsd           {report['gsd'] if report['gsd'] else 'not importable'}")
    if report["matches_pin"]:
        variant = "version and variant" if report["variant_checked"] else "version (variant unverifiable: no conda-meta)"
        lines.append(f"verdict       OK: the engine matches the pin by {variant}")
    else:
        lines.append(
            f"verdict       NOT THE PINNED BUILD: installed {b['version']}"
            + (f" {pkg.get('build')}" if pkg else "")
            + f" against the pin {pin['line'].lstrip('- ').strip()}. A run would proceed and record "
            "this build in its preflight report; if that is not what you want, recreate the "
            "environment from the file."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="the report as JSON on stdout")
    args = ap.parse_args(argv)
    report = check(read_pin())
    code = status(report)
    report["exit_status"] = code
    print(json.dumps(report, indent=2) if args.json else render(report))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
