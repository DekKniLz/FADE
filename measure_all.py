"""Consolidated measurements for the paper (single run, one machine)."""
import random, time, math, statistics
import fade
from benchmark_fade import BaselineLineal, construir, altura

SIZES = [1000, 3000, 10000, 30000, 100000]

def pct(xs, q):
    xs = sorted(xs)
    if not xs: return float('nan')
    i = min(len(xs)-1, max(0, int(round(q*(len(xs)-1)))))
    return xs[i]

def build_pair(n):
    ev = construir(n)
    tr = fade.Fade()
    t0 = time.perf_counter()
    for (t,v,w) in ev: tr.insert(t,v,w)
    ins_fade = (time.perf_counter()-t0)/n*1e6
    ba = BaselineLineal()
    t0 = time.perf_counter()
    for (t,v,w) in ev: ba.insert(t,v,w)
    ins_base = (time.perf_counter()-t0)/n*1e6
    return ev, tr, ba, ins_fade, ins_base

def mean_time(fn, reps):
    t0 = time.perf_counter()
    for _ in range(reps): fn()
    return (time.perf_counter()-t0)/reps*1e6

print("=== SCALING (means, us/query) + insertion + height ===")
rows = []
plot_ns, plot_fade, plot_base = [], [], []
for n in SIZES:
    ev, tr, ba, insf, insb = build_pair(n)
    rnd = random.Random(123)
    tmin, tmax = ev[0][0], ev[-1][0]
    wins = [(lambda a: (a, rnd.uniform(a, tmax)))(rnd.uniform(tmin, tmax)) for _ in range(64)]
    ks = [rnd.randint(1, n) for _ in range(64)]
    i = {'v':0}
    def fpt():
        a,b = wins[i['v']%len(wins)]; i['v']+=1; tr.peor_tramo(a,b)
    i2 = {'v':0}
    def fag():
        a,b = wins[i2['v']%len(wins)]; i2['v']+=1; tr.agregado(a,b,"suma")
    i3 = {'v':0}
    def fsel():
        k = ks[i3['v']%len(ks)]; i3['v']+=1; tr.select(k)
    i4 = {'v':0}
    def bpt():
        a,b = wins[i4['v']%len(wins)]; i4['v']+=1; ba.peor_tramo(a,b)
    i5 = {'v':0}
    def bag():
        a,b = wins[i5['v']%len(wins)]; i5['v']+=1; ba.agregado_suma(a,b)
    rf = 40*len(wins)
    rb = max(len(wins), (2_000_000//n))*1
    ptf = mean_time(fpt, rf); agf = mean_time(fag, rf); self_ = mean_time(fsel, rf)
    ptb = mean_time(bpt, rb); agb = mean_time(bag, rb)
    h = altura(tr); bound = 2*math.log2(n+1)
    rows.append((n,h,bound,insf,insb,ptf,ptb,agf,agb,self_,ptb/ptf))
    plot_ns.append(n); plot_fade.append(ptf); plot_base.append(ptb)
    print(f"n={n:>7} h={h} bound={bound:.1f} | WS f/b {ptf:.1f}/{ptb:.1f} "
          f"Agg f/b {agf:.1f}/{agb:.1f} Sel {self_:.2f} | {ptb/ptf:.1f}x | "
          f"ins f/b {insf:.1f}/{insb:.2f}")

print("\n=== TAIL LATENCY of WorstStretch (us): p50/p95/p99 ===")
tail = {}
for n in [10000, 100000]:
    ev, tr, ba, *_ = build_pair(n)
    rnd = random.Random(7)
    tmin, tmax = ev[0][0], ev[-1][0]
    nf = 4000 if n==10000 else 3000
    nb = 400 if n==100000 else 1500
    fs = []
    for _ in range(nf):
        a = rnd.uniform(tmin,tmax); b = rnd.uniform(a,tmax)
        t0=time.perf_counter(); tr.peor_tramo(a,b); fs.append((time.perf_counter()-t0)*1e6)
    bs = []
    for _ in range(nb):
        a = rnd.uniform(tmin,tmax); b = rnd.uniform(a,tmax)
        t0=time.perf_counter(); ba.peor_tramo(a,b); bs.append((time.perf_counter()-t0)*1e6)
    tail[n] = (pct(fs,.5),pct(fs,.95),pct(fs,.99),pct(bs,.5),pct(bs,.95),pct(bs,.99))
    print(f"n={n}: FADE p50/p95/p99 = {pct(fs,.5):.1f}/{pct(fs,.95):.1f}/{pct(fs,.99):.1f}"
          f"   base p50/p95/p99 = {pct(bs,.5):.0f}/{pct(bs,.95):.0f}/{pct(bs,.99):.0f}")

# regenerate figure from fresh means
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(6.6,3.9))
ax.plot(plot_ns, plot_fade, "o-", color="#1F4E79", lw=2, label="FADE  (O(log n))")
ax.plot(plot_ns, plot_base, "s--", color="#C55A11", lw=2, label="Linear scan, RAP-style batch recompute  (O(n))")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Number of events  n"); ax.set_ylabel("Time per WorstStretch query  (\u00b5s)")
ax.grid(True, which="both", ls=":", alpha=.5); ax.legend(frameon=False, fontsize=9, loc="upper left")
fig.tight_layout(); fig.savefig("scalability_paper.png", dpi=200)
print("\n[scalability_paper.png written]")
