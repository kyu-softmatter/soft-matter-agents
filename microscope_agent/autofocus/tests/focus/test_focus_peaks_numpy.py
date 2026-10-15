"""focus_classical's numpy peak finder matches scipy.signal.find_peaks with a prominence
floor (the code it replaced; soft-matter-agents' microscope env has no scipy)."""

import numpy as np
import pytest

from dino_autofocus.focus import classical as C

signal = pytest.importorskip("scipy.signal")


def _scipy(x: np.ndarray, floor: float) -> list[int]:
    return [int(i) for i in signal.find_peaks(x, prominence=floor)[0]]


def _ours(x: np.ndarray, floor: float) -> list[int]:
    return [i for i in C._local_maxima(x) if C._prominence(x, i) >= floor]


@pytest.mark.parametrize("seed", range(200))
def test_same_peaks_as_scipy_on_random_curves(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(3, 40))
    # small integer levels give plateaus and ties, the cases where the rules can differ
    x = rng.integers(0, 6, size=n).astype(np.float64) if seed % 2 else rng.normal(size=n)
    floor = float(rng.choice([0.0, 0.5, 1.0, 2.0]))
    assert _ours(x, floor) == _scipy(x, floor)


def test_flat_top_counts_once_at_its_middle():
    x = np.array([0.0, 1.0, 3.0, 3.0, 3.0, 3.0, 1.0, 0.0])
    assert C._local_maxima(x) == _scipy(x, 0.0) == [3]
