"""Preemptive (pause/resume) WAN transfer: greedy optimality, dominance and the closed form."""

import itertools
import math
import unittest

import numpy as np

from cwm_multidc.scripts.preemptive_transfer import contiguous_avg, preemptive_avg


def best_contiguous(c, arrival, tau, step=60.0):
    return min(contiguous_avg(c, t, tau) for t in np.arange(0.0, arrival - tau + 1e-9, step))


def exhaustive(c, arrival, tau, grain=900):
    caps = [int(min(3600, max(0, arrival - 3600 * h)) // grain) for h in range(len(c))]
    need, best = int(tau // grain), math.inf
    for alloc in itertools.product(*[range(k + 1) for k in caps]):
        if sum(alloc) == need:
            best = min(best, sum(a * grain * ci for a, ci in zip(alloc, c)) / tau)
    return best


class PreemptiveTest(unittest.TestCase):
    def test_greedy_is_optimal_and_never_worse_than_contiguous(self):
        rng = np.random.default_rng(1)
        for _ in range(120):
            hours = int(rng.integers(2, 6))
            c = rng.uniform(20, 600, hours)
            arrival = 3600.0 * int(rng.integers(1, hours + 1)) - 900.0 * int(rng.integers(0, 3))
            tau = 900.0 * int(rng.integers(1, max(2, int(arrival // 900))))
            if tau > arrival:
                continue
            g = preemptive_avg(c, arrival, tau)
            self.assertAlmostEqual(g, exhaustive(c, arrival, tau), places=9)
            self.assertLessEqual(g, best_contiguous(c, arrival, tau) + 1e-9)

    def test_closed_form_removes_sinc_attenuation(self):
        """CI = cbar + A cos(2 pi t / 24 h): over a window W of whole days, the preemptive transfer sees
        cbar - A sinc(pi tau / W); the best contiguous one sees cbar - A |sinc(pi tau / 24 h)|."""
        cbar, amp = 200.0, 80.0
        hours = np.arange(72)
        # hourly samples of a sinusoid (piecewise-constant, as in the model)
        c = cbar + amp * np.cos(2 * np.pi * (hours + 0.5) / 24)
        tau, window = 24 * 3600.0, 48 * 3600.0
        pre = preemptive_avg(c, window, tau)
        contig = best_contiguous(c, window, tau, step=3600.0)
        self.assertAlmostEqual(contig, cbar, delta=0.5)  # contiguous: a full day averages out
        hourly_sinc = math.sin(math.pi / 24) / (math.pi / 24)  # hourly sampling of the cosine
        expected = cbar - amp * hourly_sinc * math.sin(math.pi / 2) / (math.pi / 2)
        self.assertAlmostEqual(pre, expected, delta=0.5)
        self.assertLess(pre, contig - 40)

    def test_infeasible_transfer_rejected(self):
        with self.assertRaises(ValueError):
            preemptive_avg(np.array([10.0, 20.0]), 3600.0, 7200.0)


if __name__ == "__main__":
    unittest.main()
