# plan-sim-20260923-201-r5: the drag-calibration grid

*Generated from the JSON beside this file, which is authoritative (P3). Status: VALIDATED.*

| cell | stiffness | speed | step | record | steps | run |
|---|---|---|---|---|---|---|
| k1_o1 | 0.1 pN/um | 0.4 um/s | 0.002 s | 20000 s | 10000000 | skipped |
| k1_o2 | 0.1 pN/um | 4 um/s | 0.002 s | 200 s | 100000 | yes |
| k1_o3 | 0.1 pN/um | 40 um/s | 0.0004 s | 80 s | 200000 | yes |
| k2_o1 | 1 pN/um | 1 um/s | 0.0002 s | 3000 s | 20000000 | skipped |
| k2_o2 | 1 pN/um | 10 um/s | 0.0002 s | 30 s | 200000 | yes |
| k2_o3 | 1 pN/um | 100 um/s | 4e-05 s | 8 s | 200000 | yes |
| k3_o1 | 10 pN/um | 4 um/s | 2e-05 s | 200 s | 10000000 | skipped |
| k3_o2 | 10 pN/um | 40 um/s | 2e-05 s | 2 s | 100000 | yes |
| k3_o3 | 10 pN/um | 400 um/s | 4e-06 s | 0.8 s | 200000 | yes |

Every kept cell at the conservative rate: 3000 s.

## Open risks

- THE RECOVERED STIFFNESS IS NOT EVIDENCE ABOUT ANY TRAP: gamma and k_t go in and the estimator inverts the equation the integrator solved. The question the grid answers is whether the fractional error of the recovered stiffness follows sqrt(2*tau/T)/(offset/sigma) with the stiffness cancelled, which is read across the cells' result cards and not by any one of them.
- The slow row, offset one thermal width, is skipped at the conservative per-step cost. At the measured cost it is seconds a cell; it comes back when the measured cost is in the store.
- Speeds are one significant figure, so the realised offset differs from the row's label by up to 30 per cent. The record is sized for the realised offset, and each result reports it as a deviation.
- The trap is harmonic by declaration: no escape and no anharmonicity. At the fast row the soft cell's offset is about four micrometres, far outside a real trap's quadratic range.
- The viscosity cancels out of recovered over declared here and does not on the bench, where the sample temperature is neither actuated nor read.
