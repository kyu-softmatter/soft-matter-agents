# Piezo X sine — run-20260924-005 (2026-09-24)

**Plain-language report for the person.** The run log (`log.json`) beside this
file is the record, and this report is read from it. If the two disagree, the
log is right. The graph is `position_vs_time.svg`.

## What ran

The piezo stage's X axis only, on the plan you approved (mic-20260924-002):

1. a 10 µm step from rest (0.075 µm) to 10 µm
2. five sine cycles between 10 and 590 µm, centred at 300 µm, 1 cycle per
   second, 200 points per cycle (one every 5 ms), sent from software. The
   controller's waveform generator was **not** used
3. a step back to 0.5 µm

It ran from 20:09:24 to 20:09:30 UTC. You watched through the eyepiece with
the 20x dry lens and said it was working well. Y, Z, the focus and the
objective were not moved.

## Results

| | commanded | measured | within the 1 µm check after settling? |
|---|---|---|---|
| approach | 10 µm | 10.59 µm, settled within 35 ms | yes |
| sine | 1000 points, 10–590 µm | all 1000 sent, **none late**; the stage reached 9.03 to 590.56 µm | yes (ended at 9.66 µm; the last commanded point was 10 µm) |
| return | 0.5 µm | 0.61 µm, settled within 35 ms | yes |

**Tracking during the sine:** the measured position lags the commanded one.
The difference is at most **20.2 µm**, and its root-mean-square is **13.3 µm**,
worst in the middle of each sweep where the speed peaks at about 1.8 mm/s.
Each position was read about a millisecond after its point was sent, so
this lag includes the time for the stage to respond. It is a measured value,
not a spec.

The large errors shown on the two single steps (about 10 µm and 9 µm) are
their first reading, taken right after the write while the stage was still
moving. The settled readings in the table are the ones the check used.

## One mistake, mine

**The approval's written time is wrong.** In the approval text I gave you, I
wrote a fixed time of 21:00 UTC instead of the real time. The run started at
20:09 UTC, so the file says the approval came after the run. It did not: the
run controller checked that your approval matched this exact plan before
anything moved, and the log records that match. Because of the wrong
timestamp, the repository's checker refuses to accept this run as it stands.
**Correcting `approved_at` and `created_at` in your approval file to the real
time you wrote it (about 20:08 UTC) is yours to do.** I did not change it,
because that file is yours. The run folder and the approval are not committed
until that is settled.

Two smaller things this run showed:
- Windows PowerShell 5.1 saves files with a hidden marker (BOM) at the start.
  The run controller refused the first approval because of it. That was
  correct but confusing, and it is worth fixing on the reading side
- the approval had to be written three times before it existed. Next time I
  will give you a single short command

## State of the instrument now

- **Nothing is moving and no command is pending**
- piezo X is at 0.61 µm; Y and Z are where they were
- the controller's lock is back at the level it was found (locked); the port
  is closed; the controller is **still switched on**
- the microscope is released back to you

## What would come next (not started)

- correct the approval time, then commit this run
- if you want: repeat at a lower rate (for example 0.2 Hz) to see how much of
  the 13 µm lag is speed, and a step per channel while watching the image to
  confirm X/Y mapping as a separate check
- piezo Z stays off: it rests 1.7 nm below your 0 µm floor, and which way it
  approaches the objective is unmeasured
