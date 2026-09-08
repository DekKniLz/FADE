"""Peak memory of the tree, and repeated-run confidence intervals."""
import tracemalloc, time, math, statistics, random
import fade
from benchmark_fade import build_events

SIZES = [1000, 3000, 10000, 30000, 100000]

print("=== Peak Python memory attributed to the tree (tracemalloc) ===")
print(f"{'n':>8} {'peak MB':>9} {'bytes/event':>12}")
for n in SIZES:
    ev = build_events(n)                  # allocated BEFORE tracing, so not counted
    tracemalloc.start()
    tr = fade.Fade()
    for (t, v, w) in ev:
        tr.insert(t, v, w)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"{n:>8} {peak/1e6:>9.2f} {peak/n:>12.1f}")
    del tr

print("\n=== WorstStretch mean query time, R repetitions, 95% CI ===")
R = 7
tcrit = 2.447  # t_{0.975, df=6}
print(f"{'n':>8}   mean us  +/- 95% CI")
for n in SIZES:
    ev = build_events(n)
    tr = fade.Fade()
    for (t, v, w) in ev:
        tr.insert(t, v, w)
    rnd = random.Random(123)
    tmin, tmax = ev[0][0], ev[-1][0]
    wins = [(lambda a: (a, rnd.uniform(a, tmax)))(rnd.uniform(tmin, tmax)) for _ in range(64)]
    reps = 40 * 64
    samples = []
    for _ in range(R):
        i = 0
        t0 = time.perf_counter()
        for _ in range(reps):
            a, b = wins[i % 64]; i += 1; tr.worst_stretch(a, b)
        samples.append((time.perf_counter() - t0) / reps * 1e6)
    m = statistics.mean(samples)
    sd = statistics.stdev(samples)
    ci = tcrit * sd / math.sqrt(R)
    print(f"{n:>8}   {m:7.1f}  +/- {ci:4.1f}   (sd={sd:.1f}, R={R})")
