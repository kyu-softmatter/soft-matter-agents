"""Setup for every test process; nothing to import from here (T-035c).

One BLAS thread. numpy and scipy each bring an OpenBLAS that commits buffers for every CPU
thread when it is imported: about 500 MiB each on the 16-thread desktop, so about 1 GiB of
commit charge per pytest process before any test runs (measured: `import numpy` 506 MiB,
then `scipy.special` 1007 MiB; with one thread 24 / 41 MiB). With many sessions running
tests at once that charge is what runs out (0xc000070a, 0x8007000e). No test needs threaded
BLAS, so one thread is asked for here, before any test module imports numpy.

`setdefault`: a run that sets the variables itself keeps its values. pytest loads this file
before the conftest files and test modules below it.
"""

import os

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
