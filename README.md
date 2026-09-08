# FADE — Feedback-Augmented Dynamic Event tree

**FADE** is an in-memory red-black binary search tree keyed on event time and
augmented so that every node summarizes its subtree. It answers, in `O(log n)` time,
interval aggregates, order statistics, and the **worst contiguous stretch** (the run
of events with maximum accumulated severity), and it stays dynamic under
insert / delete / update.

This repository holds the reference implementation and the scripts that measure it.

> **This version is a full English refactor.** All identifiers, comments, docstrings,
> and console output were translated from Spanish to English. See
> [Refactor notes](#refactor-notes-spanish--english) for the exact renames.

---

## Files

| File | Role | Deps |
|------|------|------|
| `fade.py` | The data structure, a brute-force oracle, and self-tests. | stdlib |
| `benchmark_fade.py` | Correctness + scaling vs. a linear baseline; optional plot. | stdlib (+ matplotlib for `--plot`) |
| `measure_all.py` | Scaling means, tail latency (p50/p95/p99), and a scaling figure. | matplotlib |
| `experiments_extra.py` | Static **segment-tree** baseline and the **no-augmentation ablation**. | stdlib |
| `measure_ci_mem.py` | Peak memory and repeated-run **confidence intervals**. | stdlib |

The scripts import one another, so **keep all five files in the same folder.**

## Requirements

- **Python 3.8+** (developed and measured on 3.12).
- **matplotlib** only for the figures (`measure_all.py`, and `benchmark_fade.py --plot`).

```bash
pip install matplotlib     # optional; only for plots
```

## Quick start

```bash
python3 fade.py                      # correctness / invariant checks
```

Expected: the worked example reports the worst stretch `= 7`, five randomized
differential runs pass, the height bound holds, and it ends with `All checks passed.`

---

## Using FADE as a library

```python
from fade import Fade

tree = Fade()

# insert(timestamp, metric_value, severity_weight)
#   timestamp        : unique float key (event time)
#   metric_value     : a numeric metric sample (e.g. volume, pace)
#   severity_weight  : >0 penalizes, <0 credits
for ts, val, w in [(1,80,-1),(2,55,3),(3,60,-2),(4,90,4),(5,85,2),(6,40,-5),(7,70,1)]:
    tree.insert(float(ts), val, w)

tree.worst_stretch(0.0, 10.0)       # -> 7.0   value of the worst contiguous run in [a,b]
tree.aggregate(2.0, 5.0, "sum")     # -> 290.0 aggregate of metric values in the window
tree.select(3).t                    # -> 3.0   time of the 3rd event in chronological order

tree.update(6.0, 40, 2.0)           # rewrite the event at t=6.0
tree.delete(6.0)                    # remove the event at t=6.0
```

### API

Updates (all `O(log n)`):
- `insert(t, val, w)` — add an event; existing `t` is overwritten.
- `delete(t) -> bool` — remove the event at `t`; `False` if absent.
- `update(t, val, w) -> bool` — rewrite the event at `t`.

Queries over an inclusive window `[a, b]` (all `O(log n)`):
- `worst_stretch(a, b) -> float` — value of the maximum-severity contiguous run.
- `aggregate(a, b, op) -> float` — `op` in `"count"`, `"sum"`, `"mean"`, `"min"`, `"max"`.
- `select(k) -> Node | None` — the `k`-th event in time order (**1-indexed**).
- `query_range(a, b) -> Elem` — full window summary; fields `size, sum, mn, mx, W, P, S, B`
  (count, sum, min, max, and severity total / best prefix / best suffix / best run).

Checks: `check_rb()` (red-black invariants) and `check_augment()` (every stored
summary equals a fresh recomputation).

> `worst_stretch` returns the run's **value**, not its endpoints.

---

## Refactor notes (Spanish → English)

Everything user-facing and internal is now in English. Behavior and results are
unchanged. Renames:

**Public API (`fade.py`)**

| Before (Spanish) | After (English) |
|------------------|-----------------|
| `peor_tramo(a, b)` | `worst_stretch(a, b)` |
| `agregado(a, b, op)` | `aggregate(a, b, op)` |
| aggregate ops `"cuenta"` / `"suma"` / `"media"` | `"count"` / `"sum"` / `"mean"` |
| `Elem` / `Node` field `tam` | `size` |
| `brute_peor_tramo` | `brute_worst_stretch` |
| `brute_agregado` | `brute_aggregate` |

**Helpers and other modules**

| Before | After |
|--------|-------|
| `BaselineLineal` | `LinearBaseline` |
| `BaselineLineal.peor_tramo` / `agregado_suma` / `_rango` | `worst_stretch` / `aggregate_sum` / `_range` |
| `construir(n)` | `build_events(n)` |
| `altura(tree)` | `tree_height(tree)` |
| `cronometrar` | `time_per_call` |
| `guardar_plot` | `save_plot` |
| `autoevaluacion_correccion` | `check_correctness` |
| `autoevaluacion_rendimiento` | `benchmark_performance` |
| `SegTree.peor_tramo` / `agregado_suma` | `worst_stretch` / `aggregate_sum` |

**Unchanged** (already English): `insert`, `delete`, `update`, `select`,
`query_range`, `check_rb`, `check_augment`, `inorder`, `combine`, `combine3`, and the
internal red-black methods (`recompute`, `_left_rotate`, `_right_rotate`, `_find`,
`_minimum`, `_transplant`, `_insert_fixup`, `_delete_fixup`, `_query_prefix`,
`_query_suffix`).

All comments, docstrings, and console output were translated (for example,
`"Todas las comprobaciones pasaron correctamente."` → `"All checks passed."`).

---

## Experiments

Each script prints its results; two of them also write a figure to the current folder.

```bash
python3 fade.py                    # correctness / invariants
python3 measure_all.py             # scaling means + tail latency  -> scalability_paper.png
python3 benchmark_fade.py --plot   # scaling vs. linear baseline   -> benchmark_plot.png
python3 experiments_extra.py       # segment-tree baseline + no-augmentation ablation
python3 measure_ci_mem.py          # peak memory + repeated-run confidence intervals
```

| Script | What it produces |
|--------|------------------|
| `fade.py` | Invariant + differential-oracle checks |
| `measure_all.py` | Per-query means, tree height, tail-latency (p50/p95/p99); `scalability_paper.png` |
| `benchmark_fade.py` | Scaling table (FADE vs. linear baseline); `benchmark_plot.png` with `--plot` |
| `experiments_extra.py` | Segment-tree vs. FADE query time + build cost; insertion ablation |
| `measure_ci_mem.py` | Peak memory per size; 95% confidence intervals |

---

## Key findings

Measured on one **single-vCPU** virtualized host (Intel Xeon @ 2.8 GHz, 3.9 GiB,
Ubuntu 24.04, CPython 3.12, single-threaded). Absolute microseconds carry
interpreter/host noise; the **scaling** is the claim and is stable across runs.

**Correctness (measured).** All differential tests pass; every stored summary matches
a fresh recomputation; tree height stays under `2*log2(n+1)` at every size.

**Scaling vs. a linear recompute (measured).** FADE's WorstStretch query grows
~logarithmically while the linear baseline grows linearly; they cross between 10^3 and
3*10^3 events, and at n=10^5 FADE is ~40x faster in the mean, with a larger gap at the
tail (p99 ~185 us vs 15,420 us).

**Vs. a static segment tree (measured) - honest trade-off.** With the same summary,
the segment tree queries ~2.3-2.5x faster than FADE (tighter array layout); FADE does
not win on query speed. Its advantage is dynamism: the segment tree rebuilds in O(n)
(~0.84 s at n=10^5) to admit a new timestamp, whereas FADE inserts in O(log n) (~0.2 ms).

**Augmentation cost (measured ablation).** Plain red-black insertion is 2.4-4.9
us/event; maintaining the augmentation is ~98% of insertion time, dominated by
allocating a summary object per recompute.

**Memory (measured).** ~230 bytes/event (Theta(n) at d=1). **Stability:** 95% CIs
within +/-1-2%.

**Complexity (analytical).** O(log n) per operation; Theta(n*d) space.

---

## Caveats

- Single-core, pure-CPython microbenchmark on synthetic data: trust the trend, not the
  absolute constants.
- The prototype stores **one** metric per node (d=1); `Theta(n*d)` for larger d is
  analytical.
- Baselines are a linear scan (model of batch recompute) and a static segment tree; a
  dynamic segment tree and a Fenwick tree are not evaluated.
- `worst_stretch` returns the run's value; endpoint recovery needs extra bookkeeping and
  is not implemented.
