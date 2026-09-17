<!-- generated from plan_microscope_mic-20260917-001.json. Do not hand-edit: the
     JSON is authoritative (P3), and check 9 fails on any number that drifts. -->

# Screen the tracer diffusivity — mic-20260917-001

**Purpose** screen · **Intent** explore · **Configuration** brightfield tracking
**Status** APPROVED (appr-mic-20260917-001-r1) · **Degraded** librarian unreachable

## What is being asked

Which regime the tracers are in, to within one decade. Not what the diffusion
coefficient is — that would be a different purpose and a different plan.

## Why brightfield and not darkfield

Two configurations survived screening. Darkfield was dropped on numbers, not on
taste: its detection floor needs at least 0.5 s of exposure to reach the signal
to noise target from scattered light, while blur caps the exposure at 0.02 s for
a tracer of this size. The allowed sets do not overlap.

Brightfield leaves a usable decade of exposure, and the operating point is the
geometric middle of it: 0.007 s.

## Conditions

| what | value | where it came from |
|---|---|---|
| exposure time | 0.007 s | geometric middle of the allowed range, which rests on two estimates |
| frame rate | 50 Hz | camera specification |
| record length | 200 s | ten diffusive times, computed |
| pixel size | 0.1 um | camera specification |
| illumination power | 0.5 mW | lamp calibration |
| distance from wall | 20 um | estimate |

## The physics behind the record length

A 2 um sphere in water at 293 K, taking the viscosity as 0.001 Pa*s, diffuses at
about 0.2 um^2/s. It crosses its own diameter in about 20 s, and ten of those
gives a mean squared displacement good to roughly ten percent — inside the one
decade the question asks for.

Every one of those figures is an order of magnitude, deliberately. The viscosity
is a literature value and the temperature is a room setpoint rather than a
reading at the sample, so writing more digits would be inventing precision the
inputs do not have.

## When to stop, and what counts as success

Stop if the field drifts by more than 1 um over the record: beyond that the mean
squared displacement measures the stage instead of the sample.

Success is resolving the diffusivity to 1 count of decade. Both criteria were
written before the run, which is the only time they mean anything.

## What is being accepted knowingly

- The temperature is a setpoint, not a measurement at the sample, so the
  predicted diffusivity carries whatever the real temperature does.
- The librarian was unreachable, so both exposure bounds are estimates rather
  than literature values. The card says so rather than hiding it.
- One irreversible action is included: a reference field is bleached. It rests
  on a calibrated power, not on an estimate, which is why an individual approval
  was enough.

Total instrument time is about 300 s of acquisition plus setup.
