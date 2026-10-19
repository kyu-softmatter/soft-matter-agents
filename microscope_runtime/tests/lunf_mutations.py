"""Switch each refusal in lunf.py off, in memory, and watch its test fail.

    python microscope_agent/tests/lunf_mutations.py

Card 036 asks that every refusal test be watched failing. A test never seen
failing is not known to test anything, and this makes the watching
repeatable rather than a claim in a commit message.

The file on disk is never edited. Each mutation is an exact text replacement
that must match exactly once, or the run stops -- a mutation whose pattern has
drifted away from the code would otherwise "pass" by mutating nothing. The
named tests must fail under the mutation, and the unmutated module must pass
all of them first.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "test_lunf", Path(__file__).resolve().with_name("test_lunf.py"))
T = importlib.util.module_from_spec(_spec)
sys.modules["test_lunf"] = T
_spec.loader.exec_module(T)
SRC = T.LUNF_PATH.read_text(encoding="utf-8")

MUTATIONS = {
    "limit gate off": (
        [('    if COVERING_LIMIT is None:\n        return ("the person',
          '    return None\n    if COVERING_LIMIT is None:\n        return ("the person')],
        ["test_no_enable_without_limit", "test_no_enable_with_either_end_absent",
         "test_no_enable_with_unconfirmed_limit", "test_no_enable_on_an_inverted_range"]),
    "only the first end of the pair checked": (
        [('    for name in COVERING_LIMIT:\n', '    for name in COVERING_LIMIT[:1]:\n'),
         ('    if ends[0] > ends[1]:', '    if len(ends) < 2:')],
        ["test_no_enable_with_either_end_absent"]),
    "an inverted range accepted": (
        [('    if ends[0] > ends[1]:', '    if False:')],
        ["test_no_enable_on_an_inverted_range"]),
    "a different covering limit shipped": (
        [('COVERING_LIMIT: tuple[str, str] | None = ("laser_combiner_command_voltage_min",',
          'COVERING_LIMIT: tuple[str, str] | None = ("optical_power_max",')],
        ["test_the_shipped_module_names_the_persons_voltage_pair"]),
    "approval gate off": (
        [('    if _APPROVED is None or not', '    return None\n    if _APPROVED is None or not')],
        ["test_no_enable_on_a_clean_readback_alone"]),
    "bench gate off": (
        [('    if not _BENCH or not all(', '    return None\n    if not _BENCH or not all(')],
        ["test_no_enable_on_a_clean_readback_alone"]),
    "log gate off": (
        [('    if _LOG is None:\n        return "no log is bound',
          '    return None\n    if _LOG is None:\n        return "no log is bound')],
        ["test_no_enable_on_a_clean_readback_alone"]),
    "path gate off": (
        [('    if _PATH_READER is None:\n        return ("no light-path',
          '    return None\n    if _PATH_READER is None:\n        return ("no light-path')],
        ["test_no_enable_while_path_reaches_eyepieces", "test_no_enable_when_no_mapping_is_recorded",
         "test_no_enable_on_a_label", "test_no_enable_while_path_unreadable",
         "test_readback_is_read_and_logged_immediately_before_each_enable"]),
    "no recorded mapping treated as permissive": (
        [('    if not _EYEPIECE_FREE:\n        return (f"the light path reads state {state}, and no',
          '    if not _EYEPIECE_FREE:\n        return None\n        return (f"the light path reads state {state}, and no')],
        ["test_no_enable_when_no_mapping_is_recorded"]),
    "a state outside the mapping treated as permissive": (
        [('    if state not in _EYEPIECE_FREE:\n        return (',
          '    if state not in _EYEPIECE_FREE:\n        return None\n        return (')],
        ["test_no_enable_while_path_reaches_eyepieces"]),
    "labels accepted (integer check and key filter both off)": (
        [('    if isinstance(state, bool) or not isinstance(state, int):', '    if False:'),
         ('                      if isinstance(k, int) and not isinstance(k, bool)\n'
          '                      and isinstance(v, str)',
          '                      if isinstance(v, str)')],
        ["test_no_enable_on_a_label"]),
    "a clean read-back permits": (
        [('        reasons += [why for gate in ENABLE_GATES if (why := gate(enable))]',
          '        reasons += ([p] if (p := _path_refusal(enable)) else [])')],
        ["test_no_enable_on_a_clean_readback_alone", "test_every_refusal_reported_at_once"]),
    "read-back cached across enables": (
        [('        reading = _PATH_READER()',
          '        reading = globals().get("_CR") or globals().setdefault("_CR", _PATH_READER())')],
        ["test_readback_is_read_and_logged_immediately_before_each_enable"]),
    "read-back not logged": (
        [('        _LOG(event="light_path_readback"', '        (lambda **k: None)(event="light_path_readback"')],
        ["test_readback_is_read_and_logged_immediately_before_each_enable"]),
    "power accepted": (
        [('    unknown = sorted(k for k in params if k != "enable")', '    unknown = []')],
        ["test_power_is_refused"]),
    "opens written before closes": (
        [('        order = sorted(lid for lid in lines if lid not in enable) + enable',
          '        order = enable + sorted(lid for lid in lines if lid not in enable)')],
        ["test_enable_writes_closes_first_and_claims_no_readback"]),
    "abort writes nothing": (
        [('                _TRANSPORT.write_level(lines[lid], closed_level)\n', '                pass\n')],
        ["test_abort_blanks_every_line_first"]),
    "abort stops at the first failed line": (
        [('                row.update(written=False, error=repr(exc))\n',
          '                row.update(written=False, error=repr(exc))\n'
          '                report["blanked"].append(row)\n                break\n')],
        ["test_abort_reports_a_failed_line_and_blanks_the_rest"]),
    "an abort reported as a closed beam": (
        [('              "beam": ASSUMED_ON, "barrier": None,\n',
          '              "beam": "off", "barrier": None,\n')],
        ["test_a_blind_laser_is_assumed_on_after_any_command"]),
    "held lines written anyway": (
        [('    if not free:\n        return f"the digital lines are not free',
          '    if False:\n        return f"the digital lines are not free')],
        ["test_held_lines_are_not_ready"]),
}


def run(mod, names: list[str]) -> bool:
    """True when every named test passes against `mod`."""
    case = type("Under", (T.Gates,), {"mod": mod})
    suite = unittest.TestSuite(case(n) for n in names)
    result = unittest.TextTestRunner(stream=open(__import__("os").devnull, "w"),
                                     verbosity=0).run(suite)
    return result.wasSuccessful()


def main() -> int:
    every = sorted({n for _, names in MUTATIONS.values() for n in names})
    declared = sorted(n for n in dir(T.Gates) if n.startswith("test_"))
    if not run(T.load(SRC, "lunf_clean"), declared):
        print("the unmutated module fails its own tests; nothing below would mean anything")
        return 1
    print(f"unmutated: {len(declared)}/{len(declared)} tests pass")
    bad = 0
    for label, (edits, names) in MUTATIONS.items():
        text = SRC
        for old, new in edits:
            n = text.count(old)
            if n != 1:
                print(f"STALE         {label}: pattern matched {n} times: {old[:60]!r}")
                return 1
            text = text.replace(old, new)
        mod = T.load(text, "lunf_mutated")
        outcome = {name: run(mod, [name]) for name in names}
        caught = not any(outcome.values())
        bad += not caught
        print(f"{'WATCHED FAIL' if caught else 'NOT CAUGHT':13} {label}: "
              + ", ".join(f"{k[5:]}={'pass' if v else 'fail'}" for k, v in outcome.items()))
    print(f"{len(MUTATIONS) - bad}/{len(MUTATIONS)} mutations caught; "
          f"{len(every)} of {len(declared)} tests are named by a mutation")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
