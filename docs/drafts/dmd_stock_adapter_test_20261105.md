# DMD: trying the stock v75 adapter with Mightex's SDK DLLs (2026-11-05)

For the runtime session in `microscope_runtime/`, on the microscope computer.
The person chose this route on 2026-11-05 ("SDK DLLs on v75"), over moving the
engine to a v71 core, after reading the readiness report's DMD section.

## What this tests, and the odds

The run engine loads from pymmcore-plus's Micro-Manager folder, whose core is
device interface 75. That folder has the stock `mmgr_dal_MightexPolygon.dll`
(interface 75), written for the Polygon400. Loaded once this morning without
Mightex's SDK libraries beside it, it crashed Python while enumerating devices.

Micro-Manager's own page for that adapter says the Polygon400 needs two Mightex
DLLs and one SDK folder copied into the Micro-Manager folder before the adapter
loads at all. Its Polygon1000 note describes the same copy, after which the
device appeared in the configuration wizard **and then failed to initialise:
"Unable to communicate with the device (35)"** -- and the note ends there.
So the one public record of this exact route on a Polygon1000 is a failure.
This test is cheap (file copies and one guarded load) and reversible, which is
why it is worth half an hour; it is not expected to work. Have the v71-core
route ready as the next step.

## Before anything is loaded

1. The person has said, in the runtime session's own window, that the bench is
   that session's. A relayed hand-over is none.
2. PolyScan is **not** running (it holds the DMD's USB link; one holder at a
   time). The Tweez 300 GUI and NIS-Elements may stay as they are: neither
   touches the DMD.
3. Every light source is off: light engine, LUN-F lasers, dia lamp. The DMD is
   a mirror array and lights nothing itself, but nothing should be lit while an
   untested driver enumerates USB devices.
4. The run lock is free.

## Step 1 -- find the two folders (opens nothing)

```powershell
python -c "from pymmcore_plus import find_micromanager; print(find_micromanager())"
```

That is the engine's folder (expected: the `Micro-Manager_2.0.3_20260806`
copy). Then find Mightex's libraries in the lab's older installation and the
setup folder:

```powershell
Get-ChildItem -Recurse "C:\Program Files\Micro-Manager-2.0" | Where-Object { $_.Name -match 'Polygon|Mightex|BLSDriver' } | Select-Object FullName, Length
Get-ChildItem -Recurse "C:\Users\Takatori lab\Desktop\Maintanance\Setup\DMD" | Select-Object FullName, Length
```

Wanted, by Micro-Manager's page: `MT_Polygon400_IMGC.dll`,
`MT_Polygon400_SDK.dll`, the folder `MT_Polygon400_SDK\` (with its
`DSIG…` subfolder), and for the Polygon1000 also `mt_polygon1000_sdd.dll`,
`MT_Polygon1000_SDK.dll`, `Mightex_BLSDriver_SDK.dll`. Record every path found
with its size and sha256 (`Get-FileHash`). If the Polygon400 pair is missing
everywhere on the computer, stop: the stock adapter cannot load without them,
and the test is over before it starts.

## Step 2 -- copy, never move

Copy (do not move) each file and the SDK folder into the engine's folder from
step 1. Write the list of what was copied into the run folder you will create
in step 4, so the copies can be removed exactly. Nothing in the older
installation changes.

## Step 3 -- does the adapter now load and see a device? (a subprocess, a timeout)

Run this in a separate process so a crash kills only it. Use raw `pymmcore`,
not the engine: this step only asks the adapter which device names it offers,
and reports; it loads no device. Enumeration may still touch the USB bus,
which is why the preconditions above hold here too.

```powershell
python -X faulthandler -c "import pymmcore, sys; c = pymmcore.CMMCore(); c.setDeviceAdapterSearchPaths([sys.argv[1]]); print('adapters has MightexPolygon:', 'MightexPolygon' in c.getDeviceAdapterNames()); print('devices:', list(c.getAvailableDevices('MightexPolygon'))); print('descriptions:', list(c.getAvailableDeviceDescriptions('MightexPolygon')))" "<engine folder from step 1>"
```

Outcomes:
- **Crash (access violation) again** -> the DLLs did not change the failure.
  Go to cleanup; the route is closed.
- **Loads, lists no device** -> the adapter runs but does not see a Polygon1000.
  Go to cleanup; the route is closed.
- **Lists a device name** -> note the exact name (expected something like
  `MightexPolygon`); go to step 4.

## Step 4 -- one guarded load through the engine, DMD alone

The approved configuration names the Mightex vendor library
(`Device,MightexPolygon1000,MightexPolygon1000,MightexPolygon1000`). The stock
adapter is a different library, so **the approved file cannot test it**: a
one-device test configuration is needed, and it loads only after the person
approves its hash under `approvals/`, like any configuration.

Write it (the device name is the one step 3 printed):

```
# DMD-only test configuration, 2026-11-05: the stock MightexPolygon adapter on the v75 core
Property,Core,Initialize,0
Device,MightexPolygon1000,MightexPolygon,<device name from step 3>
Property,Core,Initialize,1
```

Print its sha256 and ask the person to write an approval for it (artifact
`mm_config_approval`, the hash under `configuration.sha256`). Then load it
through the engine's reader, which logs the load into `runs/`:

```powershell
$env:PYTHONUTF8 = "1"
python -P microscope_runtime/src/read_devices.py --run-id run-20261105-NNN --mm-config <the test .cfg>
```

(`-P` is needed on this branch: the script's folder holds `operator.py`, which
otherwise shadows Python's own `operator` module and crashes the import. The
readiness report records this as the runtime session's to fix.)

Outcomes:
- **"Unable to communicate with the device (35)"** or any initialisation error
  -> the documented Polygon1000 outcome. The stock adapter speaks Polygon400
  and cannot drive this device. Cleanup; the route is closed; the v71 core is
  next.
- **The DMD initialises and reports properties** -> it works. Then the real
  configuration has to change its line 8 to the stock library and device name,
  which changes its hash, so the person approves the new file; the old
  approval stays for the old bytes. Record the working DLL list in the run
  folder, because the pymmcore-plus folder is replaceable and the copies would
  be lost with it.

## Cleanup after a failure

Delete exactly the files and the folder copied in step 2, from the engine's
folder only, so it returns to the state every validated load used. Leave the
older installation untouched. Write the outcome -- which step, which message --
into the run folder or `microscope_runtime/failures.jsonl`, so nobody tries
this route again without knowing it was tried.

## If it fails: the next route

The device registry (`librarian_agent/kb/staging/devices.v0.json`, the `dmd`
row) records that on this bench, on 2026-09-07, raw `pymmcore==11.1.1.71.2`
with `C:\Program Files\Micro-Manager-2.0` loaded the full
`DMD_dualcam_LUNF.cfg` at 31 devices, the DMD included. That is a change to the
engine's Micro-Manager backend (`devices/micromanager.py`, six pymmcore-plus
call sites) and to its version pin, so it is the runtime session's work on the
person's decision, and every load validated on the v75 core would be
re-validated on the 2023-12-23 adapters.
