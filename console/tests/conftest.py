"""Setup for every test process; nothing to import from here.

One BLAS thread: numpy asks for a buffer per CPU thread when it is imported, which adds up to
about a gigabyte of commit charge per pytest process on a 16-thread machine, and several
sessions run tests at once. No test needs threaded BLAS. `setdefault` keeps a run's own values.
"""

import os

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
