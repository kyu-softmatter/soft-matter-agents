"""Is the engine here, and which build is it -- the first thing to run on a new machine.

    python3 -m src.engine_check          # from simulation_agent/
    python3 -m src.engine_check --json

HOOMD-blue is not on PyPI (plan.md 7, 2026-09-22), so `uv sync` cannot bring
it and `pyproject.toml` structurally cannot name it. What names it is
`src/environment.yml` beside this file: one conda-forge environment holding
the engine, gsd and the three pipeline dependencies, so one interpreter runs
the validator, the mock and the engine. This module reads the pin from that
file -- the single place the pin lives -- and compares it with what the
interpreter running it can import.

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
ENVIRONMENT = HERE / "environment.yml"
ENVIRONMENT_REL = "simulation_agent/src/environment.yml"
ENV_NAME = "soft-matter-agents"
# conda-forge builds hoomd 7.2.0 for these and no others. win-64 was tried
# and fails to solve (plan.md 7, 2026-09-22).
PLATFORMS = ("linux-64", "osx-64", "osx-arm64")

# `- hoomd=7.2.0=*cpu*`, with or without the build, with or without a
# trailing comment. Parsed with a regex and not a YAML library on purpose:
# the file is a flat conda spec, and pulling PyYAML into the pipeline's
# dependencies to read one line would put a dependency in pyproject.toml for
# the sake of the file that exists because pyproject.toml cannot hold the
# engine.
PIN = re.compile(r"^\s*-\s*hoomd\s*=\s*([0-9][^=\s#]*)\s*(?:=\s*([^\s#]+))?\s*(?:#.*)?$")


def read_pin(path: pathlib.Path = ENVIRONMENT) -> dict:
    """The hoomd line of environment.yml, as {version, build, line, file}."""
    for line in path.read_text().splitlines():
        m = PIN.match(line)
        if m:
            return {"version": m.group(1), "build": m.group(2), "line": line.strip(),
                    "file": ENVIRONMENT_REL}
    raise LookupError(f"no `- hoomd=<version>[=<build>]` line in {path}")


def install_lines(pin: dict) -> list[str]:
    """What to type, from the repository root. One place, quoted by the backend too."""
    spec = f"hoomd={pin['version']}" + (f"={pin['build']}" if pin["build"] else "")
    return [
        f"conda env create -f {ENVIRONMENT_REL}     # or: mamba env create -f ..., micromamba create -f ...",
        f"conda activate {ENV_NAME}     # or, with no shell init: conda run -n {ENV_NAME} python3 -m src.engine_check",
        "cd simulation_agent && python3 -m src.engine_check",
        f'# the engine alone, into an environment you already have: micromamba install "{spec}"'
        f'  (mamba install / pixi add "{spec}" likewise; official 7.2.0 forms)',
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
    ok = build["version"] == pin["version"]
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
            + ", ".join(PLATFORMS) + " and not win-64. From the repository root:"
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
