"""
FADE self-evaluation
====================

This script measures the behavior of FADE's algorithms in two ways:

  (1) CORRECTNESS. Re-runs fade.py's checks (red-black + augmentation
      invariants, contrasted against a brute-force oracle).

  (2) PERFORMANCE. Compares the running time of FADE's queries (O(log n))
      against a LINEAR baseline that recomputes over the event log (O(n) per
      query). That baseline models the method a batch-report system such as RAP
      uses de facto: segment the log and sweep it once to produce each result.

  Metrics measured: time per WorstStretch, Aggregate and SelectByTime query;
  insertion throughput; and tree height against the bound 2*log2(n+1).

Usage:  python3 benchmark_fade.py            # table on the console
        python3 benchmark_fade.py --plot     # also writes benchmark_plot.png

No external dependencies except matplotlib for --plot.
"""

import argparse
import bisect
import math
import random
import statistics
import time

import fade  # FADE implementation (same folder)


# --------------------------------------------------------------------------
# Linear baseline (model of RAP-style batch recompute).
# --------------------------------------------------------------------------
class LinearBaseline:
    """Keeps the events in a time-sorted array and answers each query with a
    linear pass (single sweep), like a batch-report system that recomputes over
    the whole log."""

    def __init__(self):
        self.ts = []      # sorted times
        self.vals = []    # values aligned with ts
        self.ws = []      # severity weights aligned with ts

    def insert(self, t, val, w):
        i = bisect.bisect_left(self.ts, t)
        self.ts.insert(i, t)      # O(n): keep the array sorted
        self.vals.insert(i, val)
        self.ws.insert(i, w)

    def _range(self, a, b):
        lo = bisect.bisect_left(self.ts, a)
        hi = bisect.bisect_right(self.ts, b)
        return lo, hi

    def worst_stretch(self, a, b):
        lo, hi = self._range(a, b)
        best = 0.0            # empty stretch allowed
        acc = 0.0
        for i in range(lo, hi):   # Kadane O(n): a single pass
            acc = max(0.0, acc + self.ws[i])
            if acc > best:
                best = acc
        return best

    def aggregate_sum(self, a, b):
        lo, hi = self._range(a, b)
        s = 0.0
        for i in range(lo, hi):   # O(n)
            s += self.vals[i]
        return s

    def select(self, k):
        return self.ts[k - 1]     # O(1) after sorted O(n) insertion


# --------------------------------------------------------------------------
# Measurement helpers.
# --------------------------------------------------------------------------
def time_per_call(func, repeats):
    t0 = time.perf_counter()
    for _ in range(repeats):
        func()
    return (time.perf_counter() - t0) / repeats


def build_events(n, seed=7):
    rnd = random.Random(seed)
    # unique, increasing times with random gaps (real stream)
    events = []
    t = 0.0
    for _ in range(n):
        t += rnd.uniform(0.05, 0.20)
        val = rnd.uniform(0, 100)          # e.g. volume or pace
        w = rnd.uniform(-3, 3)             # severity
        events.append((t, val, w))
    return events


def tree_height(tree):
    def h(x):
        if x is None:
            return 0
        return 1 + max(h(x.left), h(x.right))
    return h(tree.root)


# --------------------------------------------------------------------------
# (1) Correctness.
# --------------------------------------------------------------------------
def check_correctness():
    print("== (1) Algorithm correctness ==")
    fade.test_worked_example()
    for s in range(5):
        fade.test_random(seed=s)
    fade.test_height_bound()
    print("   -> All correctness checks passed.\n")


# --------------------------------------------------------------------------
# (2) Performance.
# --------------------------------------------------------------------------
def benchmark_performance(sizes=(1000, 3000, 10000, 30000, 100000)):
    print("== (2) Performance: FADE (O(log n)) vs linear baseline (O(n)) ==")
    rows = []
    for n in sizes:
        events = build_events(n)

        # ---- build both structures and measure insertion ----
        tree = fade.Fade()
        t0 = time.perf_counter()
        for (t, v, w) in events:
            tree.insert(t, v, w)
        t_ins_fade = (time.perf_counter() - t0) / n * 1e6   # us/insertion

        base = LinearBaseline()
        t0 = time.perf_counter()
        for (t, v, w) in events:
            base.insert(t, v, w)
        t_ins_base = (time.perf_counter() - t0) / n * 1e6

        h = tree_height(tree)
        bound = 2 * math.log2(n + 1)

        # ---- prepare random queries over windows [a,b] ----
        rnd = random.Random(123)
        tmin, tmax = events[0][0], events[-1][0]
        windows = []
        for _ in range(64):
            a = rnd.uniform(tmin, tmax)
            b = rnd.uniform(a, tmax)
            windows.append((a, b))
        ks = [rnd.randint(1, n) for _ in range(64)]

        # FADE: many repeats (each query is cheap)
        rep_fade = 40
        def q_fade_ws():
            a, b = windows[q_fade_ws.i % len(windows)]; q_fade_ws.i += 1
            tree.worst_stretch(a, b)
        q_fade_ws.i = 0
        t_ws_fade = time_per_call(q_fade_ws, rep_fade * len(windows)) * 1e6

        def q_fade_ag():
            a, b = windows[q_fade_ag.i % len(windows)]; q_fade_ag.i += 1
            tree.aggregate(a, b, "sum")
        q_fade_ag.i = 0
        t_ag_fade = time_per_call(q_fade_ag, rep_fade * len(windows)) * 1e6

        def q_fade_sel():
            k = ks[q_fade_sel.i % len(ks)]; q_fade_sel.i += 1
            tree.select(k)
        q_fade_sel.i = 0
        t_sel_fade = time_per_call(q_fade_sel, rep_fade * len(ks)) * 1e6

        # Linear baseline: fewer repeats (each query is expensive)
        rep_base = max(1, min(20, 2_000_000 // n))
        def q_base_ws():
            a, b = windows[q_base_ws.i % len(windows)]; q_base_ws.i += 1
            base.worst_stretch(a, b)
        q_base_ws.i = 0
        t_ws_base = time_per_call(q_base_ws, rep_base * len(windows)) * 1e6

        def q_base_ag():
            a, b = windows[q_base_ag.i % len(windows)]; q_base_ag.i += 1
            base.aggregate_sum(a, b)
        q_base_ag.i = 0
        t_ag_base = time_per_call(q_base_ag, rep_base * len(windows)) * 1e6

        rows.append(dict(n=n, h=h, bound=bound,
                         ins_fade=t_ins_fade, ins_base=t_ins_base,
                         ws_fade=t_ws_fade, ws_base=t_ws_base,
                         ag_fade=t_ag_fade, ag_base=t_ag_base,
                         sel_fade=t_sel_fade,
                         speedup_ws=t_ws_base / t_ws_fade))

    # ---- print table ----
    print(f"\n{'n':>8} | {'height':>6} {'bound':>6} | "
          f"{'WorstStretch us (FADE/base)':>28} | {'Aggregate us (FADE/base)':>25} | "
          f"{'Sel us':>7} | {'x faster':>9}")
    print("-" * 112)
    for f in rows:
        print(f"{f['n']:>8} | {f['h']:>6} {f['bound']:>6.1f} | "
              f"{f['ws_fade']:>12.2f} / {f['ws_base']:>12.2f} | "
              f"{f['ag_fade']:>11.2f} / {f['ag_base']:>10.2f} | "
              f"{f['sel_fade']:>7.2f} | {f['speedup_ws']:>8.1f}x")
    print("\nInsertion (us/event):")
    for f in rows:
        print(f"   n={f['n']:>7}:  FADE {f['ins_fade']:.3f}   "
              f"linear baseline {f['ins_base']:.3f}")
    return rows


def save_plot(rows, path="benchmark_plot.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ns = [f["n"] for f in rows]
    ws_fade = [f["ws_fade"] for f in rows]
    ws_base = [f["ws_base"] for f in rows]

    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    ax.plot(ns, ws_fade, "o-", color="#1F4E79", lw=2, label="FADE  (O(log n))")
    ax.plot(ns, ws_base, "s--", color="#C55A11", lw=2, label="Linear baseline (RAP-style)  (O(n))")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Number of events  n")
    ax.set_ylabel("Time per WorstStretch query (us)")
    ax.set_title("Self-evaluation: WorstStretch query scalability")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    print(f"\n[plot written to {path}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", action="store_true", help="write benchmark_plot.png")
    args = ap.parse_args()

    print("=" * 68)
    print(" FADE SELF-EVALUATION")
    print("=" * 68 + "\n")
    check_correctness()
    rows = benchmark_performance()
    if args.plot:
        save_plot(rows)
    print("\nDone.")


if __name__ == "__main__":
    main()
