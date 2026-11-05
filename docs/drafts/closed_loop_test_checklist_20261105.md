# Closed-loop test — setup checklist (2026-11-05)

Checklist for getting the experiment-simulation closed loop ready to test on
branch `closed-loop-validation`, worktree `D:\closed-loop-validation`, on the
microscope computer. Every item says what counts as passing. Read the results
off a run, not off this file.

**One limit on this pass:** nothing here opens a device, moves a stage,
switches a light or sends to the tweezers. The hardware section checks only
what can be seen without opening anything. The live open test is a separate
step: the person has to say, in the window of the session doing it, that the
bench belongs to that session.

## 1. Hardware connection (nothing opened)

- [ ] 1.1 The PC sees the devices: cameras, NI PCIe-6323 board, stage and
      focus drives, serial (COM) ports, LUN-F laser unit. Read from Windows'
      device list.
- [ ] 1.2 The drivers and software are installed: Micro-Manager and the
      version the code expects, NI-DAQmx, NIS-Elements, and the camera SDKs.
- [ ] 1.3 Which control programs are running now (NIS-Elements,
      Micro-Manager, the Tweez300 GUI). NIS holds the NI board while it runs,
      which blocks Micro-Manager's blanking lines.
- [ ] 1.4 The Tweez300 server port (127.0.0.1:2070) is listening. Checked
      from the port list; nothing is connected to it.
- [ ] 1.5 The Micro-Manager hardware configuration files the run engine
      names exist where it looks for them.
- [ ] 1.6 The person's safety policy and approvals are present and readable:
      `microscope_runtime/envelope/safety.json`, `microscope_runtime/approvals/`.
- [ ] 1.7 The run lock is free: no stale lock from an earlier run.
- [ ] 1.8 The run engine's own tests pass on the mock backend.

## 2. Simulation connection

- [ ] 2.1 WSL2 `Ubuntu-24.04` is installed and starts.
- [ ] 2.2 The `sim` pixi environment exists. HOOMD imports and reports
      7.2.0, CPU build.
- [ ] 2.3 Whether the environment covers this worktree's path, or a run from
      here would need a fresh install.
- [ ] 2.4 A short engine smoke run finishes: one particle, Brownian motion,
      a few thousand steps.
- [ ] 2.5 The simulation agent's own check scripts pass.

## 3. Bridge

- [ ] 3.1 The bridge board runs and lists every thread with whose turn it is.
- [ ] 3.2 Every thread ledger and round passes the validator.
- [ ] 3.3 The inbox folders a round delivers into exist on both sides.
- [ ] 3.4 Write down which results and plans are waiting to cross.

## 4. Librarian (knowledge store) connection

- [ ] 4.1 The launcher in `.mcp.json` finds `sh` and a Python that imports
      `mcp`, `jsonschema` and `referencing`.
- [ ] 4.2 The server starts and its self-test passes.
- [ ] 4.3 The store's entries pass their checks, and the index and pages are
      current.
- [ ] 4.4 Which folder a running session's server reads. A server started
      from `D:\soft-matter-agents` reads `main`'s store, not this branch's.
- [ ] 4.5 The query log is readable, and every past call carries an issued
      caller id.

## 5. Other things to check

- [ ] 5.1 The repository is sound on this branch: the validator ends
      `0 failed`; also the strict run, the rejected-fixture run and the
      history checks.
- [ ] 5.2 The interpreters: which `python` is on PATH, and whether it has
      `jsonschema`, `referencing` and `mcp`.
- [ ] 5.3 The knowledge snapshots on the microscope and simulation sides
      stand on the same store version, and their hashes check.
- [ ] 5.4 The clocks: Windows and WSL agree, and the PC clock is synced.
- [ ] 5.5 There is enough disk space for runs on D: and in WSL.
- [ ] 5.6 Git: the branch matches its remote, `main` is untouched, and the
      commit hooks are configured (or not) in this worktree.
- [ ] 5.7 One whole loop on paper or mock: question → simulation plan →
      bridge round → microscope plan → mock run → result card → librarian.
      Note each step that exists and each that is missing.
