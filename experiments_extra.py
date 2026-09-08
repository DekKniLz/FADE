"""
Two experiments requested for the paper:

(A) STATIC SEGMENT TREE baseline for the range queries, using the SAME summary
    monoid as FADE (fade.combine), so the comparison is semantics-identical.
    The combine is non-commutative (left = older), so the iterative range query
    accumulates the left and right canonical pieces in order.

(B) NO-AUGMENTATION ABLATION: a red-black tree with identical node objects and
    rotations as FADE, but with the augmentation-maintenance calls turned into
    no-ops. The gap in insertion time isolates the cost of maintaining W/P/S/B
    (and size/sum/min/max) on the update path.
"""
import bisect, math, random, time
import fade
from fade import Elem, combine, IDENT, Fade
from benchmark_fade import construir, altura

SIZES = [1000, 3000, 10000, 30000, 100000]


# ---------- (A) static segment tree over time-sorted events ----------
def _leaf(ev):
    t, val, w = ev
    return Elem(1, val, val, val, w, max(0.0, w), max(0.0, w), max(0.0, w))

class SegTree:
    def __init__(self, events):
        ev = sorted(events)
        self.ts = [e[0] for e in ev]
        self.n = len(ev)
        self.t = [IDENT] * (2 * self.n)
        for i, e in enumerate(ev):
            self.t[self.n + i] = _leaf(e)
        for i in range(self.n - 1, 0, -1):
            self.t[i] = combine(self.t[2 * i], self.t[2 * i + 1])

    def _query_pos(self, l, r):          # inclusive [l, r], preserves order
        resl, resr = IDENT, IDENT
        l += self.n; r += self.n + 1
        while l < r:
            if l & 1:
                resl = combine(resl, self.t[l]); l += 1
            if r & 1:
                r -= 1; resr = combine(self.t[r], resr)
            l >>= 1; r >>= 1
        return combine(resl, resr)

    def query(self, a, b):
        lo = bisect.bisect_left(self.ts, a)
        hi = bisect.bisect_right(self.ts, b) - 1
        if lo > hi:
            return IDENT
        return self._query_pos(lo, hi)

    def peor_tramo(self, a, b):
        return self.query(a, b).B

    def agregado_suma(self, a, b):
        return self.query(a, b).sum


# ---------- (B) no-augmentation ablation ----------
class FadeNoAug(Fade):
    """Same RB structure/rotations as FADE, but augmentation upkeep is a no-op."""
    def recompute(self, x):        # overrides staticmethod; called as self.recompute(x)
        pass
    def _recompute_up(self, x):
        pass


def mean_time(fn, reps):
    t0 = time.perf_counter()
    for _ in range(reps):
        fn()
    return (time.perf_counter() - t0) / reps * 1e6


# ---------- correctness of the segment tree vs FADE ----------
def check_segtree():
    ev = construir(2000, seed=99)
    tr = Fade()
    for (t, v, w) in ev:
        tr.insert(t, v, w)
    st = SegTree(ev)
    rnd = random.Random(5)
    ts = [e[0] for e in sorted(ev)]
    ok = True
    for _ in range(500):
        a = rnd.uniform(ts[0], ts[-1]); b = rnd.uniform(a, ts[-1])
        if not (math.isclose(st.peor_tramo(a, b), tr.peor_tramo(a, b)) and
                math.isclose(st.agregado_suma(a, b), tr.agregado(a, b, "suma"))):
            ok = False; break
    print(f"(A) segment tree matches FADE on 500 random windows: {ok}")
    return ok


def experiment_segtree():
    print("\n=== (A) STATIC SEGMENT TREE vs FADE (query us, build us/event) ===")
    for n in SIZES:
        ev = construir(n)
        tr = Fade()
        for (t, v, w) in ev:
            tr.insert(t, v, w)
        t0 = time.perf_counter()
        st = SegTree(ev)
        build_us = (time.perf_counter() - t0) / n * 1e6
        rnd = random.Random(123)
        ts = st.ts
        wins = [(lambda a: (a, rnd.uniform(a, ts[-1])))(rnd.uniform(ts[0], ts[-1]))
                for _ in range(64)]
        i = {'v': 0}
        def f_seg():
            a, b = wins[i['v'] % 64]; i['v'] += 1; st.peor_tramo(a, b)
        j = {'v': 0}
        def f_fade():
            a, b = wins[j['v'] % 64]; j['v'] += 1; tr.peor_tramo(a, b)
        reps = 40 * 64
        seg = mean_time(f_seg, reps); fad = mean_time(f_fade, reps)
        print(f"  n={n:>7}: WorstStretch  seg={seg:6.1f}  fade={fad:6.1f} us   "
              f"| seg build={build_us:5.2f} us/event  (rebuild is O(n))")


def experiment_ablation():
    print("\n=== (B) ABLATION: insertion us/event, FADE vs no-augmentation RB ===")
    print(f"  {'n':>7} | {'FADE':>8} | {'no-aug':>8} | {'aug overhead':>12} | share")
    for n in SIZES:
        ev = construir(n)
        # FADE (with augmentation)
        tr = Fade()
        t0 = time.perf_counter()
        for (t, v, w) in ev:
            tr.insert(t, v, w)
        full = (time.perf_counter() - t0) / n * 1e6
        # no augmentation
        nr = FadeNoAug()
        t0 = time.perf_counter()
        for (t, v, w) in ev:
            nr.insert(t, v, w)
        noaug = (time.perf_counter() - t0) / n * 1e6
        ov = full - noaug
        share = ov / full * 100.0
        print(f"  {n:>7} | {full:8.1f} | {noaug:8.1f} | {ov:8.1f} us | {share:5.1f}%")


if __name__ == "__main__":
    check_segtree()
    experiment_segtree()
    experiment_ablation()
