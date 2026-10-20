# 057 — the combiner's per-line power has a word after all, and four lines answered to it

renumbered 054 to 057 on 2026-10-20 by manager-librarian-scope-20261019-4 when it took these four from branch `claude/rea-evidence-cards` (`f0af976c`) into main, on the person's word (Q-20261019-10, `02aaf2ee`): main had already issued 053-055 to other cards. Every card number below was renumbered with it; nothing else changed. Still a draft: landing it is not issuing it.

status: **draft, not issued** · drafted 2026-10-16 by the same side session
as 056, which is not a seated manager-librarian. The request was relayed, not
heard · **for manager-librarian to issue, revise or refuse**. 056's section
*Before anything enters* applies here in full: REA is not a source until the
person opens it directly to architecture, its ceiling is E3, and its live log
is in no commit.

## GOAL

The store says the confocal combiner's lines are reachable only as blanking,
and that per-line power is deliberately not transmitted because the word the
power interface expects is undocumented. REA recovered that word from the
acquisition software's own driver, sent it with the acquisition software
closed, and the person watched all four lines light at 5.0 V and stay dark at
0.0 V on 2026-10-13. Decide what the store says now. Keep apart what the run
showed and what it only seemed to show.

## THE ENTRIES THIS TOUCHES

| entry | grade, source | what REA bears on |
|---|---|---|
| `lunf_per_line_power_is_not_transmittable` | E3, `prior_run:agentic-microscope@safety-2026-09-03` | **contradicted on "reachable only as blanking".** The second half, *the vendor does not document the word and the prior project chose not to guess it*, stays true as history: the vendor still documents nothing. What changed is that the word is no longer a guess. **The entry holds two claims** (rule 1), and superseding it may mean splitting them |
| `lunf_analog_outputs_are_not_cabled_to_the_combiner` | E3, prior_run 2026-09-02 | **not contradicted.** It is about the DAQ's analog outputs `Dev1 ao0-ao3`. REA's power route is a separate DAC behind an FT4222 SPI bridge, so it explains the negative result rather than refuting it. At most, its conditions gain one sentence naming where the power does go |
| `lunf_line_map_and_blanking_polarity` | E3, prior_run | **the map is corroborated, and the polarity only half.** See *What the run did not show* |
| `devices.v0.json`, row `laser_combiner` | staging table | `driver` already says *per-line power over SPI*. `driver_note` says *the power half is deliberately not transmitted*, and `line_power.note` says *this system does not transmit the per-line power word*. `line_select` keeps `lines`, `open_level` and `closed_level` **absent on purpose**, to be filled *from a bench confirmation of each line, by eye*. The gap `laser_combiner_manual_absent` stands: the word came from a binary, not a manual |
| the nine `confocal_power_at_sample_<line>nm_<obj>_full_level` | E2, worksheet of 2026-09-09 | each cites the not-transmittable entry. **"Full level" is a level in the acquisition software, and how that number maps to volts was not traced** (FINDINGS, *How a power value gets to volts*). So none of the nine can yet be tied to 5.0 V |

## THE EVIDENCE, AND WHERE IT IS

At REA `5cdf237`: `lunf_direct/FINDINGS.md` (blob sha256
`e390a72ace62d4dedcbaa8a5b58b42db16197a61afa13dbdfbf7879efd21472c`),
`lunf_direct/GPIO.md` (`ac7abf3d74e874dfaae967bcbe49736a785f61ba173e4352ce99713fbb6edaec`),
`lunf_direct/run_blink.py` (`fba408e0bc1effe706dfed32a7d05b228fce990da6cc1b8cbc8783bb4ca066ed`)
and `lunf_direct/lunf_direct.py`.

- **Wiring** [the vendor's device database, read from a read-only copy].
  `C:\ProgramData\Laboratory Imaging\Platform\DeviceDatabase_6_00.dat`, table
  `dev_PhysicalDevice`, row `LUN-F`. Power is `FT4222_00294-BOA/AO_A_0..3` for
  405/488/561/640. Blanking is `Dev1/port0/line2/4/6/8`, in the same order.
  That database puts **405 on line2**, which agrees with the entry against
  the two prior-project database copies that put it on line1.
- **The word** [binary]. `v6_w32_NIApi.dll` 6.20.02,
  `CNIDAQResource_AOChannel::WriteValue` at rva `0x1796d0`. It is a single
  3-byte SPI write on FT4222 interface A: `[0x30 | (1 << ch), (code >> 4) & 0xFF,
  (code & 0xF) << 4]`, with `code = round(volts * 4095 / 5)`. That is a 12-bit
  quad DAC, 0 to 5 V full scale, one-hot channel address. The comparison to an
  AD5684-style part is REA's inference from the layout.
- **Live, 2026-10-13, 18:00 and 18:05.** `run_blink.py`, with NIS closed and no
  GPIO replay. For each line, 5 repetitions of: on at 0 V for 1 s, off for
  0.5 s, on at 5.0 V for 1 s, off for 0.5 s. All four lines lit on the 5.0 V
  pulses and stayed dark on the 0 V pulses and between them, in both runs.
  FINDINGS says the person watched and *reported "working very well"*. The
  uncommitted log matches the shape: 432 non-dry-run lines from 18:00:19 to
  18:06:40, and 40 `set_volts` at 5.0 V, which is 4 lines × 5 repetitions × 2
  runs.
- **Who holds what.** NIS holds FT4222 A/B/C and the DAQ lines while it runs.
  This agrees with the existing finding in
  `microscope-20260924-3-20260924.json` (item at line 92).

## WHAT THE RUN DID NOT SHOW: write each into the conditions

- **The blanking polarity is half shown, and FINDINGS overstates it.** In
  `lunf_direct.py`, `on()` writes the voltage and then unblanks (line = 1);
  `off()` blanks (line = 0) and then writes 0 V. So the run produced three
  states: line 1 at 0 V (dark), line 1 at 5 V (lit), line 0 at 0 V (dark).
  **It never produced line 0 at 5 V.** It therefore shows that the DAC word
  controls emission while the line is held at 1. It does not show that line 0
  darkens a lit line, so it shows neither "1 = on" nor that the blanking line
  gates emission at all. FINDINGS' banner says it *confirms blanking polarity
  active-high*. Do not carry that sentence. The missing state is one step:
  line 0 at a low voltage, by eye or with a frame, in a run the person
  approves.
- **How "lit" was judged is not recorded**: by eye at what, through which
  path, and whether each line was identified by colour. *All four lit* is the
  person's report as FINDINGS gives it, not a frame.
- **NIS's shutdown and the fiber shutter.** FINDINGS says NIS was closed. It
  does not say whether NIS was closed normally or killed, nor what state the
  fiber shutter was in. The store already holds that the fiber shutter
  survives a force-kill. Ask before writing any claim about it.
- **A cold boot without NIS is untested.** NIS had run on that boot, so
  GPIO3 was probably still high from its start-up sequence. Whether direct
  control needs `BoardGpio().nis_startup_sequence()` after a power-up is open
  (GPIO.md step 3). What GPIO2 and GPIO3 are wired to is unknown.
- **Only 0 V and 5.0 V were sent.** Nothing between them, so nothing about
  linearity, and no power was measured.
- **Version.** REA's `CLAUDE.md` calls the install NIS-Elements 6.10, and the
  DLL FINDINGS read is 6.20.02. Cite the DLL's version, not the product's.

## WHAT IT MEANS FOR SAFETY, which this card does not move

- **The person's limit is already in volts**: 0 to 5 V on the combiner's power
  input, `laser_combiner_command_voltage_min` / `_max`, decided 2026-09-24.
  What is new is that a gate *could* compare a commanded level against it.
  Whether one does is a microscope card's decision. The envelope's values are
  the person's.
- **The run used full scale on every line.** That was the person's run,
  watched by the person. It sets nothing here.
- REA's `lunf_direct_limits.json` is REA's own gate and binds nothing here.

## WHAT WOULD BE AFFECTED IF THE STORE CHANGES

Read-only, for relay. **Edit none of these.**

- `microscope_agent/src/devices/lunf.py`. Line 1 says *blanking only*.
  Lines 24-29 say *Per-line power, never* and cite the entry. Lines 53-55, in
  gate 1, say *this gate cannot compare anything against the limit. Power is
  not transmitted*. Lines 379-382 refuse any power parameter citing the
  entry. All of that stays correct as code until a card changes it.
- `microscope_agent/src/devices/lunf_live_checklist.md:19` (row 0b, the level
  set by hand), `:104` and `:121`.
- `microscope_agent/src/orchestrator.py:1914`. A comment cites the entry for
  why `*_blanking` channels exist. That reasoning survives the change.
- `microscope_agent/src/session_036_laser.py`. It uses the route the person
  chose on 2026-09-24: NIS sets the level and opens the fiber shutter, then is
  force-killed. REA's route sets the level itself with NIS closed. Whether
  that changes the route is the person's decision, not the store's.
- `microscope_agent/rulings.jsonl` lines 27, 28, 29 and 33. Line 29 discarded
  *the FT4222 SPI transport, the nine candidate DAC framings* **on the
  grounds of this entry**, and line 28 discarded `FULL_SCALE_V = 5.0` on the
  same grounds. Those rulings are append-only records. A new ruling is a
  microscope seat's to write. Worth checking: whether REA's word is one of the
  prior project's nine candidate framings (agentic-microscope `config/lunf/`
  at `a7b880b`, the files those rulings were recorded from, open under 10.2).
- `kb/guides/safety_laser_combiner.md` is rendered from the store and moves
  with the publish.
- `plan.md:165`, architecture's. It cites the entry to show that `*_blanking`
  is a real spelling. That point stands either way.

## TASK, for the librarian seat, once REA is open

1. Rule each item: the wiring, the word, the live result, NIS holding the
   interfaces. Transfer, downgrade or discard (10.2.1), naming the slot and
   the 10.3 rule. The word and the full scale are machine-readable only in a
   vendor binary and in REA's prose. Decide which, if either, is a source
   (056, point 5).
2. **Supersede or conflict** `lunf_per_line_power_is_not_transmittable`.
   Consider splitting it: *the lines are reachable only as blanking*
   (contradicted), and *the vendor documents no word, and the prior project
   chose not to guess* (true, and now history). Write which and why.
3. **Leave `lunf_analog_outputs_are_not_cabled_to_the_combiner` standing.**
   If anything, add one sentence of conditions naming where the power does go.
4. **`lunf_line_map_and_blanking_polarity`.** The map gains corroboration: the
   vendor database's mapping, and four lines that answered on their mapped
   channels. The polarity gains nothing that this card can defend, because
   the line-0 state was never shown. **Do not fill `line_select` from REA.**
   The table says to fill it from a bench confirmation of each line by eye,
   and the run is half of one.
5. Write the falsifiers: a line that lights at 0 V with line 1, or stays dark
   at 5 V with line 1. Separately, for the polarity: a line that stays lit at
   line 0.
6. Read-only: list the cards citing the entry, at their pins, for relay.

## CONTRACT

- A claim about a control path and its wiring. The full scale, 5 V, is the
  DAC's range and not a limit. The limit is the person's, already written.
- No value moves in the nine power entries. Their conditions may gain one
  sentence saying that the level-to-volts mapping is not traced.

## CONSTRAINTS

As 056's. Dead ends go in `failures.jsonl` with `task: 057`.

## REPORT

Each item and its ruling. Split or not, and the relation. What the polarity
entry says now. The cards citing the old entry. The commit and `kb_version`.
One sentence: what is not yet on disk.
