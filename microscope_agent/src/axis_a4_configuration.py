"""A4: configuration suitability -- whether this configuration can be driven and verified.

4.5.3 gives this axis device combination, optical-path exclusivity and
automatability. The inequality list below is derived from that cell rather than
declared here (4.5.2.1), and each entry names where it comes from.

**This axis is answered by the service, not by reading the store.** Every other
axis so far called axis_common.kb_entry(), which opens kb/entries/*.json -- and
reading the files is not the service answering (0.3), so those cards belong to
the degraded path whatever they say. This one takes a --responses file holding
what the librarian actually returned, refuses any response not stamped with the
pin it was asked at, and never opens the store. That is why `degraded` can be
empty here and could not be before.

What the pass found, and it is the content of the card rather than a caveat:

  The three selectors that define `widefield_inline` all read back, and not one
  of the three read-backs establishes what it has to establish. The port
  returns a position number and which element that position holds is unknown;
  `csuw1_bright` and `csuw1_disk_position` are one mechanism under two names, so
  setting one and reading the other agrees with itself and means nothing; and
  the disk-out label serves widefield fluorescence and brightfield alike, so
  confirming the label confirms nothing about which configuration is loaded.

  2.1 says an unverified state does not proceed. So A4 returns a constraint
  rather than an abstention: this configuration is reachable, and its loaded
  state is not verifiable by read-back. Verification has to come from acquiring.

  That is the opposite of what 001 expected of A4 -- it was picked as the axis
  most likely to return an interval because the device registry is the one
  table with real content. The registry lives in kb/staging/, and the service
  answers every question about it `absent`, saying in the gap itself that it
  searched kb/entries only and does not search outside the store. So it is not
  reachable through the service, and the pin does not change that. Every
  registry-dependent bound below therefore abstains with a gap the service
  itself reported, while the bounds that rest on entries return.

  That paragraph used to cite the server's source instead of the server's
  answer, which was a 6.2 rule 3 crossing and is recorded as one in
  failures.jsonl. The answer says the same thing and is inside the boundary.

A4 has no numeric output, and for a day it had no card either: `returned`
required an `interval`, and an interval needs a unit that means nothing for a
selector name. The axis refused rather than misreport, and the refusal is in
failures.jsonl. `4cc39a0` opened the slot, and what had actually been blocking
was narrower than discrete-versus-numeric -- an interval's `basis` could only
name entries in numbers[], and this axis's numbers[] is empty, so a new field
alone would have failed in the same place. `basis` now also takes
`kb:<entry_id>`, resolving against this card's own kb_refs.

The two bounds take different shapes on purpose. Exclusivity is an
`allowed_set` because S4 **intersects** it with other axes' ranges and sets.
Verifiability is a `precondition` because it restricts no value and instead
requires something of the plan, so it **propagates**: folded into a set it
would be dropped the first time an intersection was taken, and "establish the
loaded state by acquiring" would vanish from the plan without a trace.

It reads contracts/ and the recorded responses, and imports no device
(7.2 rule 2).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
from datetime import datetime, timezone                           # noqa: E402
from pathlib import Path                                          # noqa: E402


def _load(name: str, filename: str):
    path = os.path.join(_HERE, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                               # type: ignore[union-attr]
    return module


axc = _load("_mic_axis_common", "axis_common.py")

AXIS = "a4"

OWNED = (
    axc.Inequality(
        id="devices_present",
        parameter="device_set",
        statement="every device this configuration declares exists in the registry and has a "
                  "control channel",
        needs=("device_registry", "control_channel"),
        derived_from="4.5.3 A4 'device combination'",
    ),
    axc.Inequality(
        id="path_tuple_valid",
        parameter="selector_states",
        statement="the selector states this configuration needs form a tuple the optical-path "
                  "table lists, so light actually reaches the detector",
        needs=("optical_path_valid_tuples",),
        derived_from="4.5.3 A4 'optical path exclusivity', and 4.6's rule that S3.0 and the "
                     "orchestrator read one table",
    ),
    axc.Inequality(
        id="selector_exclusivity",
        parameter="lock_group",
        statement="no two selectors this configuration must hold at once contend for one "
                  "exclusive resource",
        needs=("lock_groups",),
        derived_from="4.5.3 A4 'optical path exclusivity'",
    ),
    axc.Inequality(
        id="selector_automatable",
        parameter="commanded_selectors",
        statement="every selector the plan must set can be set without a human, and any "
                  "condition attached to that claim holds",
        needs=("device_registry", "automatable_condition"),
        derived_from="4.5.3 A4 'automatability'",
    ),
    axc.Inequality(
        id="selector_verifiable",
        parameter="verified_selectors",
        statement="every selector the plan must set can be confirmed to be in the state it was "
                  "set to; an unverified state does not proceed (2.1)",
        needs=("read_back",),
        derived_from="4.5.3 A4 'automatability', sharpened by 2.1: read-back is what makes a "
                     "selector state verified, and 4.6.6 rule 5 routes the rest to a manual sheet",
    ),
)

GAP_IDS = {
    "device_registry": "device_registry_not_an_entry",
    "control_channel": "control_channel_not_an_entry",
    "read_back": "read_back_not_an_entry",
    "optical_path_valid_tuples": "optical_path_table_not_an_entry",
    "automatable_condition": "automatable_condition_not_an_entry",
}

# The five names this axis asked for are not entries, and the service answered
# `absent` to all five. They are in this agent's own snapshot, published by the
# librarian and pinned by sha256 -- which is why 4.3.1 grew a fifth gap kind on
# 2026-09-19, after these exact three queries sent a caller outside for what it
# already held. The gap now says where it is; whether the bound can rest on it
# is a separate question and the answer is below.
PUBLISHED = {
    "device_registry": {"snapshot": "kb/exports/snapshot_microscope_agent.json",
                        "table": "devices", "sha256": "69c56ea681458edf3921d0b7a0150468a4fae18b4c6e71a28e769a00a599d37b"},
    "control_channel": {"snapshot": "kb/exports/snapshot_microscope_agent.json",
                        "table": "devices", "column": "driver", "sha256": "69c56ea681458edf3921d0b7a0150468a4fae18b4c6e71a28e769a00a599d37b"},
    "read_back": {"snapshot": "kb/exports/snapshot_microscope_agent.json",
                  "table": "devices", "column": "read_back", "sha256": "69c56ea681458edf3921d0b7a0150468a4fae18b4c6e71a28e769a00a599d37b"},
    "automatable_condition": {"snapshot": "kb/exports/snapshot_microscope_agent.json",
                              "table": "devices", "column": "automatable_condition",
                              "sha256": "69c56ea681458edf3921d0b7a0150468a4fae18b4c6e71a28e769a00a599d37b"},
    "optical_path_valid_tuples": {"snapshot": "kb/exports/snapshot_microscope_agent.json",
                                  "table": "optical_paths", "sha256": "020c5369ab0645b06061c96e5af94df5f05761ec0b167e7c76f05dba0e69ec2c"},
}

def read_published(pin: str, table: str) -> tuple[dict | None, str]:
    """The table the service pointed at, read out of this agent's own snapshot.

    `in_published_table` means *read it from your own copy*, and 4.3.1 grew
    the kind for exactly these five names after `absent` sent a caller
    outside the building for what it already held. The next action the kind
    prescribes is this function, so the axis performs it instead of treating
    the answer as silence.

    ONLY AT ITS OWN PIN. The envelope moves when the librarian publishes and
    a pinned card does not, so reading the current copy for a card pinned
    older would cite a table the pin never saw -- which is the second of the
    two errors `gaps_from` refuses, and refusing it there and committing it
    here would be the same mistake with a different hand. When the two
    disagree it reads nothing and says which is which.
    """
    snapshot = axc.AGENT / "envelope" / "snapshot.json"
    if not snapshot.exists():
        return None, "there is no envelope/snapshot.json to read it from"
    snap = json.loads(snapshot.read_text())
    if snap.get("kb_version") != pin:
        return None, (f"this agent's envelope is at {snap.get('kb_version')} and this fan-out is "
                      f"pinned to {pin}, so reading it here would cite a table this pin never "
                      f"saw")
    held = (snap.get("tables") or {}).get(table)
    if held is None:
        return None, f"the envelope's snapshot carries no `{table}` table"
    return json.loads(held["text"]), (f"read from envelope/snapshot.json tables.{table} at {pin}, "
                                      f"sha256 {held['sha256'][:12]}")


def devices_finding(config: str, pin: str) -> str:
    """What the channel table actually says about this configuration's devices."""
    table, how = read_published(pin, "devices")
    if table is None:
        return f"The axis could not read it either: {how}."
    rows = {c["id"]: c for c in table.get("channels", []) or []}
    declared = (axc.configuration(config).get("devices") or [])
    lines = []
    for device in declared:
        row = rows.get(device)
        if row is None:
            lines.append(f"{device}: not a channel row")
            continue
        cond = row.get("automatable_condition")
        lines.append(f"{device}: driver {row.get('driver')!r}, automatable "
                     f"{row.get('automatable')!r}, read_back {row.get('read_back')!r}"
                     + (f", automatable_condition {cond!r}" if cond else ""))
    return (f"THE AXIS READ IT, {how}, and this is what it says for the {len(declared)} devices "
            f"this configuration declares -- " + "; ".join(lines) + ".")


def path_finding(config: str, pin: str) -> str:
    """Whether the optical-path table lists this configuration, and with what."""
    table, how = read_published(pin, "optical_paths")
    if table is None:
        return f"The axis could not read it either: {how}."
    row = next((c for c in table.get("configurations", []) or [] if c.get("id") == config), None)
    if row is None:
        listed = sorted(c.get("id") for c in table.get("configurations", []) or [])
        return (f"THE AXIS READ IT, {how}, and this configuration is not in it: the table lists "
                f"{listed}.")
    keys = sorted(k for k in row if k != "id")
    return (f"THE AXIS READ IT, {how}, and the table does list {config!r}, carrying {keys}. What "
            f"it does not carry is the thing this bound is about: a list of selector-state "
            f"TUPLES that are known to pass light. A configuration being listed is not a "
            f"validated combination.")


STAGING_NOTE = (
    "THIS PARAGRAPH SAID `absent` UNTIL 2026-09-20 AND THE SERVICE HAD STOPPED SAYING IT. At "
    "kbv-49feb73662b7 the answer was `absent`; at this fan-out's own pin the service answers "
    "`in_published_table` to all five and names the snapshot, the table, the column and a "
    "sha256. The card carried both claims at once -- its kb_gaps said in_published_table while "
    "the reason beside them said the service answered absent -- because `evaluate` collected "
    "every gap into one dict called `absent` and never looked at the kind. One file, two "
    "contradictory statements about the same call, and nothing could catch it because each "
    "half was well formed. Where the answer is: this agent's own envelope/snapshot.json, under "
    "tables.devices and tables.optical_paths, published by the librarian and pinned by sha256. "
    "Read there, "
    "all six devices this configuration declares are channel rows with drivers, all six are "
    "`automatable: full`, all six carry `read_back: true`, and the DMD alone carries "
    "`automatable_condition: core_requirement` -- full only on a core pinned to device interface "
    "71, which is the trap this bound was written to catch.\n\n"
    "**The gap says `absent` and not `in_published_table`, deliberately.** This axis wrote the "
    "second for a day and it was wrong twice: the service said `absent`, so the kind was the "
    "axis inventing a classification nobody made; and the sha256 it carried came from the "
    "current snapshot while this card is pinned older, so the card cited a table its own pin "
    "never saw. The other seat refused the identical move on its PFS gap and was right. When "
    "the pin reaches a version whose export answers to these names the service will return "
    "that kind itself, and then it belongs in the gap.\n\n"
    "**So why does the bound still abstain.** Because a bound has to say what it rests on, and "
    "`basis` takes a name in numbers[] or `kb:<entry_id>` and nothing else. A published table is "
    "neither. Citing the row's `entry_ref` instead would be false grounding -- check 54 exists "
    "because a bound resting on something the card never obtained is the defect an empty basis "
    "was going to be, and the values here (driver, automatable, read_back) are in the table and "
    "not in those entries. So the axis can read the answer and cannot ground a bound on it. The "
    "missing piece is a third basis form for a published table, and that is contracts/ and the "
    "manager's (6.2). This is the same shape as the discrete-constraint slot one step along: the "
    "answer existed, the card had no lawful way to say it."
)


def evaluate(goal: dict, config: str, caller_id: str, responses: dict, pin: str) -> axc.AxisRun:
    """Every inequality A4 owns, each with a constraint or a reason it has none."""
    run = axc.AxisRun(axis=AXIS, caller_id=caller_id, config=config, kb_version=pin,
                      owned=OWNED, degraded=[])

    # ONE DICT CALLED `absent` HELD BOTH KINDS AND THAT IS HOW THE CARD CAME TO
    # CONTRADICT ITSELF. `in_published_table` is not an absence: its next action
    # is *read your own snapshot*, while `absent`'s is *search outside, then ask
    # a person* (4.3.1). Collapsing them made the reason say the service
    # answered absent while the kb_gaps beside it said otherwise.
    gaps = {g["observable"]: g for g in responses["gaps"]}
    absent = gaps                      # still every unanswered name, for `needs`
    run.kb_refs = axc.refs_from(responses, pin)
    run.kb_gaps = axc.gaps_from(responses, pin, caller_id, GAP_IDS, PUBLISHED)

    for ineq in OWNED:
        missing = [n for n in ineq.needs if n in absent]

        if ineq.id == "selector_exclusivity":
            # What the entry states at E3 is the arrangement: one channel carries two lock
            # groups, and a lock group belongs to an element. The entry explicitly declines to
            # stamp the scheduling consequence as a reading, so this axis does not cite it as
            # one -- what follows from the arrangement alone is a constraint on how a plan may
            # name a selector, and that is what is returned.
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="returned",
                # NOT an allowed_set, and the difference is the whole of this
                # bound. A set is a menu: S4 intersects it and S5 picks one
                # value, and picking here is meaningless because BOTH values
                # are true at once -- this channel is in both lock groups
                # simultaneously and nobody chooses between them. Emitted as a
                # set through revision 1, S5 read two values, found nothing to
                # order them by and sent a tie to the person under 4.5.1 (c)
                # that no answer could settle. What the bound actually asks is
                # a property of the plan's FORM, which is what a precondition
                # is for: it propagates instead of intersecting, and A4 already
                # uses one on this same card for verified_selectors.
                precondition={
                    "parameter": "lock_group",
                    "requires": (
                        "Name every selector this configuration holds as an ELEMENT and never as "
                        "a channel: stand_ti2e carries optical_path and stage at the same time, "
                        "so a command that names the channel has not said which lock it takes, "
                        "and the scheduler cannot serialise what it cannot identify."
                    ),
                    "basis": ["kb:stand_ti2e_lock_groups"],
                },
                reason="Exclusivity on this configuration has to be evaluated per element and "
                       "cannot be evaluated per channel. stand_ti2e carries two lock groups at "
                       "once -- its optical elements in optical_path, the motor stage in stage, "
                       "because the piezo rides on the motor stage -- so a plan that names the "
                       "channel has not said which lock its command takes. The constraint is "
                       "therefore on the plan's form: a selector this configuration holds is "
                       "named as an element. Both groups hold simultaneously and NEITHER is "
                       "chosen, which is why this returns a precondition and not a set of two "
                       "values; a set would say pick one, and there is nothing to pick. Note what is NOT claimed here: the entry's own "
                       "validity_conditions mark the scheduling consequence -- that stage moves "
                       "serialise with port and filter changes -- as a design consequence rather "
                       "than a reading, and it is not stamped as one, so this axis does not "
                       "return it as a bound.",
            ))
            continue

        if ineq.id == "selector_verifiable":
            # Three independent entries, one conclusion. Returned rather than abstained: the
            # axis has grounds and the grounds say the bound bites.
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="returned",
                precondition={
                    "parameter": "verified_selectors",
                    "requires": ("establish the loaded state by acquiring an image, not by reading "
                                 "a selector back; a plan that treats a returned position as a "
                                 "verification is refused"),
                    "basis": ["kb:csuw1_port_slots",
                              "kb:csuw1_disk_position_is_the_bright_selector",
                              "kb:csuw1_disk_position_states"],
                },
                reason="None of the three selectors that define this configuration is verifiable "
                       "by read-back, and each fails differently. (1) The port is drivable and "
                       "readable in full, and read-back returns a position number while which "
                       "element that position holds is not known -- two of its three states send "
                       "zero light to one camera, so the position does not say which. (2) "
                       "csuw1_bright and csuw1_disk_position are one mechanism under two names, "
                       "so setting one and reading the other shows an agreement that means "
                       "nothing, and which name micromanager addresses is unsettled. (3) The "
                       "disk-out position serves widefield fluorescence and brightfield alike, "
                       "so a read-back confirming the label confirms nothing about which "
                       "configuration is loaded. 2.1 makes an unverified state one that does not "
                       "proceed, so the bound is: on this configuration the loaded state is "
                       "established by acquiring, not by read-back, and a plan that treats a "
                       "returned position as a verification is refused. Readable-but-not-"
                       "verifiable is a sharper case than unreadable -- a reply exists and does "
                       "not answer the question asked -- and it is the reason this returns "
                       "instead of abstaining.",
            ))
            continue

        if missing:
            in_table = [n for n in missing if gaps[n].get("kind") == "in_published_table"]
            nowhere = [n for n in missing if gaps[n].get("kind") != "in_published_table"]
            said = []
            if in_table:
                said.append(f"{', '.join(in_table)} -> in_published_table, which names where it "
                            f"is rather than saying it is missing")
            if nowhere:
                said.append(f"{', '.join(nowhere)} -> absent")
            reason = (f"the service was asked for {', '.join(missing)} at {pin} and answered: "
                      + "; ".join(said) + ". ")
            if in_table:
                reason += (devices_finding(config, pin) if ineq.id != "path_tuple_valid"
                           else path_finding(config, pin)) + " "
            reason += STAGING_NOTE
            if ineq.id == "selector_automatable":
                reason += (
                    " One selector is answered and it is not enough: the port is automatable in "
                    "full with read-back at E3. The bound is over every selector the plan "
                    "commands, and which selectors those are comes from the optical-path table, "
                    "which is the same absent table. An automatable field also carries a "
                    "condition in the registry -- the DMD's full automatability holds only on a "
                    "core pinned to device interface 71 -- and screening on the bare field would "
                    "pass a plan whose preflight then fails when it opens the device."
                )
            if ineq.id == "path_tuple_valid":
                reason += (
                    " What the entries do give is one required value rather than the tuple: "
                    "disk-out is a required selector value on this configuration rather than a "
                    "configuration of its own. A required value is not a validated combination, "
                    "and the combination is what this bound is about."
                )
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="no_input", missing=missing, reason=reason,
            ))
            continue

        run.outcomes.append(axc.Outcome(
            inequality_id=ineq.id, parameter=ineq.parameter, state="failed",
            reason="every input is present and this axis has no code to emit the constraint: "
                   "that is a gap in this file, not an abstention (4.5.2.1)",
        ))

    # THE NOTES BELOW ARE COMPUTED FROM THIS RUN AND WERE HARD-CODED PROSE
    # UNTIL 2026-09-20. They described one fan-out -- a pin of
    # kbv-49feb73662b7, five answers of `absent`, a store of 25 entries
    # against 49 -- and they travelled unchanged onto every card this module
    # wrote afterwards, so the first card of the next question asserted a pin
    # it was not at and answers it did not get. Prose that outlives its run is
    # the failure this repository keeps counting; a note that cannot be
    # computed should not be a note.
    served = sorted(responses.get("entries") or {})
    kinds: dict[str, list[str]] = {}
    for g in responses.get("gaps") or []:
        kinds.setdefault(g.get("kind", "?"), []).append(g["observable"])
    run.notes.append(
        f"Answered by the librarian service rather than by reading the store, which is what "
        f"makes degraded empty here: {len(served)} entries came back with their own grades and "
        + "; ".join(f"{len(v)} came back {k} ({', '.join(sorted(v))})"
                    for k, v in sorted(kinds.items()))
        + f", all at the pinned {pin}, and every call is in "
          f"librarian_agent/queries/log.jsonl under this caller_id."
    )

    in_table = kinds.get("in_published_table") or []
    if in_table:
        run.notes.append(
            f"{len(in_table)} of the answers are `in_published_table` and not absences: the "
            f"service named the snapshot, the table and the column, and the axis read there. "
            f"An earlier note on this module said the server loads index.json and entries/ only "
            f"so no version of it could serve these -- that stopped being true when the kind was "
            f"added, and the answers above are the service doing exactly what it could not. "
            f"What still stops the bounds is not the reading: `basis` takes a numbers[] name or "
            f"`kb:<entry_id>` and a published table is neither, so the value is in hand and "
            f"cannot be grounded. Raised with manager-microscope."
        )

    envelope = axc.AGENT / "envelope" / "snapshot.json"
    if envelope.exists():
        held = json.loads(envelope.read_text())
        if held.get("kb_version") != pin:
            run.notes.append(
                f"This agent's envelope is at {held.get('kb_version')} and this fan-out is "
                f"pinned to {pin}, so entries entered since the pin exist and cannot be cited "
                f"here -- the pin does not move while its siblings hold it (check 33). That is "
                f"the cost of the pin and it is worth paying only while the siblings need it."
            )

    run.notes.append(
        "constraints[] is empty while bounds returned, and that is the contract rather than "
        "the axis: interval requires {parameter, unit, basis} with numeric min/max, and A4's "
        "answers are discrete and per-selector. The ledger item forbids additional properties, "
        "so the constraint is carried in reason where S4 can read it and cannot intersect it. "
        "Raised with manager-microscope."
    )
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A4: configuration suitability (4.5.3).")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--caller-id", required=True)
    parser.add_argument("--kb-version", required=True,
                        help="the pin to answer at. Not read from the store: the store moves and "
                             "siblings have to agree (check 33)")
    parser.add_argument("--prefix", default="",
                        help="filename prefix for a re-run of the whole fan-out, e.g. v2_ "
                             "(4.5.5); empty overwrites the card in place")
    parser.add_argument("--revision", type=int, default=1,
                        help="the card revision; v<N> in the caller_id follows it")
    parser.add_argument("--responses", required=True, type=Path,
                        help="what the librarian returned for this caller_id at that pin")
    args = parser.parse_args(argv)

    goal = json.loads(args.goal.read_text())
    if goal.get("card") != "goal":
        print(f"{args.goal} is not a goal card", file=sys.stderr)
        return 2
    try:
        responses = axc.load_responses(args.responses, args.kb_version, args.caller_id)
    except axc.AxisError as exc:
        print(f"no card written: {exc}", file=sys.stderr)
        return 3
    run = evaluate(goal, args.config, args.caller_id, responses, args.kb_version)
    axc.report(run)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return axc.write(run, goal, goal.get("qid", ""), created_at, args.revision, args.prefix)


if __name__ == "__main__":
    raise SystemExit(main())
