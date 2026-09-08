"""
Autoevaluacion del funcionamiento de FADE
==========================================

Este script mide el funcionamiento de los algoritmos de FADE de dos formas:

  (1) CORRECCION. Reejecuta las comprobaciones de fade.py (invariantes
      rojo-negro + aumentacion, contrastadas contra un oraculo de fuerza bruta).

  (2) RENDIMIENTO. Compara el tiempo de ejecucion de las consultas de FADE
      (O(log n)) frente a una LINEA BASE lineal que recalcula sobre el registro
      de eventos (O(n) por consulta). Esa linea base modela el metodo que
      emplea de facto un sistema de reporte por lotes como RAP: segmentar el
      registro y recorrerlo una vez para producir cada resultado.

  Metricas medidas: tiempo por consulta de PeorTramo, Agregado y OrdenPorTiempo;
  rendimiento de insercion; y altura del arbol frente a la cota 2*log2(n+1).

Uso:  python3 benchmark_fade.py            # tabla en consola
      python3 benchmark_fade.py --plot     # ademas guarda benchmark_plot.png

No requiere dependencias externas salvo matplotlib para --plot.
"""

import argparse
import bisect
import math
import random
import statistics
import time

import fade  # implementacion de FADE (misma carpeta)


# --------------------------------------------------------------------------
# Linea base lineal (modelo del recalculo por lotes tipo RAP).
# --------------------------------------------------------------------------
class BaselineLineal:
    """Mantiene los eventos en un arreglo ordenado por tiempo y responde cada
    consulta con un recorrido lineal (una sola pasada), como un sistema de
    reporte por lotes que recalcula sobre el registro completo."""

    def __init__(self):
        self.ts = []      # tiempos ordenados
        self.vals = []    # valores alineados con ts
        self.ws = []      # pesos de severidad alineados con ts

    def insert(self, t, val, w):
        i = bisect.bisect_left(self.ts, t)
        self.ts.insert(i, t)      # O(n): mantener el arreglo ordenado
        self.vals.insert(i, val)
        self.ws.insert(i, w)

    def _rango(self, a, b):
        lo = bisect.bisect_left(self.ts, a)
        hi = bisect.bisect_right(self.ts, b)
        return lo, hi

    def peor_tramo(self, a, b):
        lo, hi = self._rango(a, b)
        best = 0.0            # tramo vacio permitido
        acc = 0.0
        for i in range(lo, hi):   # Kadane O(n): una sola pasada
            acc = max(0.0, acc + self.ws[i])
            if acc > best:
                best = acc
        return best

    def agregado_suma(self, a, b):
        lo, hi = self._rango(a, b)
        s = 0.0
        for i in range(lo, hi):   # O(n)
            s += self.vals[i]
        return s

    def select(self, k):
        return self.ts[k - 1]     # O(1) tras insertar ordenado en O(n)


# --------------------------------------------------------------------------
# Utilidades de medicion.
# --------------------------------------------------------------------------
def cronometrar(funcion, repeticiones):
    t0 = time.perf_counter()
    for _ in range(repeticiones):
        funcion()
    return (time.perf_counter() - t0) / repeticiones


def construir(n, seed=7):
    rnd = random.Random(seed)
    # tiempos unicos y crecientes con separacion aleatoria (flujo real)
    eventos = []
    t = 0.0
    for _ in range(n):
        t += rnd.uniform(0.05, 0.20)
        val = rnd.uniform(0, 100)          # p. ej. volumen o ritmo
        w = rnd.uniform(-3, 3)             # severidad
        eventos.append((t, val, w))
    return eventos


def altura(arbol):
    def h(x):
        if x is None:
            return 0
        return 1 + max(h(x.left), h(x.right))
    return h(arbol.root)


# --------------------------------------------------------------------------
# (1) Correccion.
# --------------------------------------------------------------------------
def autoevaluacion_correccion():
    print("== (1) Correccion de los algoritmos ==")
    fade.test_worked_example()
    for s in range(5):
        fade.test_random(seed=s)
    fade.test_height_bound()
    print("   -> Todas las comprobaciones de correccion pasaron.\n")


# --------------------------------------------------------------------------
# (2) Rendimiento.
# --------------------------------------------------------------------------
def autoevaluacion_rendimiento(tam=(1000, 3000, 10000, 30000, 100000)):
    print("== (2) Rendimiento: FADE (O(log n)) vs linea base lineal (O(n)) ==")
    filas = []
    for n in tam:
        eventos = construir(n)

        # ---- construir ambas estructuras y medir insercion ----
        arbol = fade.Fade()
        t0 = time.perf_counter()
        for (t, v, w) in eventos:
            arbol.insert(t, v, w)
        t_ins_fade = (time.perf_counter() - t0) / n * 1e6   # us/insercion

        base = BaselineLineal()
        t0 = time.perf_counter()
        for (t, v, w) in eventos:
            base.insert(t, v, w)
        t_ins_base = (time.perf_counter() - t0) / n * 1e6

        h = altura(arbol)
        cota = 2 * math.log2(n + 1)

        # ---- preparar consultas aleatorias sobre ventanas [a,b] ----
        rnd = random.Random(123)
        tmin, tmax = eventos[0][0], eventos[-1][0]
        ventanas = []
        for _ in range(64):
            a = rnd.uniform(tmin, tmax)
            b = rnd.uniform(a, tmax)
            ventanas.append((a, b))
        ks = [rnd.randint(1, n) for _ in range(64)]

        # FADE: muchas repeticiones (cada consulta es barata)
        rep_fade = 40
        it = iter([])
        def q_fade_pt():
            a, b = ventanas[q_fade_pt.i % len(ventanas)]; q_fade_pt.i += 1
            arbol.peor_tramo(a, b)
        q_fade_pt.i = 0
        t_pt_fade = cronometrar(q_fade_pt, rep_fade * len(ventanas)) * 1e6

        def q_fade_ag():
            a, b = ventanas[q_fade_ag.i % len(ventanas)]; q_fade_ag.i += 1
            arbol.agregado(a, b, "suma")
        q_fade_ag.i = 0
        t_ag_fade = cronometrar(q_fade_ag, rep_fade * len(ventanas)) * 1e6

        def q_fade_sel():
            k = ks[q_fade_sel.i % len(ks)]; q_fade_sel.i += 1
            arbol.select(k)
        q_fade_sel.i = 0
        t_sel_fade = cronometrar(q_fade_sel, rep_fade * len(ks)) * 1e6

        # Baseline lineal: menos repeticiones (cada consulta es cara)
        rep_base = max(1, min(20, 2_000_000 // n))
        def q_base_pt():
            a, b = ventanas[q_base_pt.i % len(ventanas)]; q_base_pt.i += 1
            base.peor_tramo(a, b)
        q_base_pt.i = 0
        t_pt_base = cronometrar(q_base_pt, rep_base * len(ventanas)) * 1e6

        def q_base_ag():
            a, b = ventanas[q_base_ag.i % len(ventanas)]; q_base_ag.i += 1
            base.agregado_suma(a, b)
        q_base_ag.i = 0
        t_ag_base = cronometrar(q_base_ag, rep_base * len(ventanas)) * 1e6

        filas.append(dict(n=n, h=h, cota=cota,
                          ins_fade=t_ins_fade, ins_base=t_ins_base,
                          pt_fade=t_pt_fade, pt_base=t_pt_base,
                          ag_fade=t_ag_fade, ag_base=t_ag_base,
                          sel_fade=t_sel_fade,
                          speedup_pt=t_pt_base / t_pt_fade))

    # ---- imprimir tabla ----
    print(f"\n{'n':>8} | {'altura':>6} {'cota':>6} | "
          f"{'PeorTramo us (FADE/base)':>26} | {'Agregado us (FADE/base)':>24} | "
          f"{'Sel us':>7} | {'x mas rapido':>11}")
    print("-" * 110)
    for f in filas:
        print(f"{f['n']:>8} | {f['h']:>6} {f['cota']:>6.1f} | "
              f"{f['pt_fade']:>11.2f} / {f['pt_base']:>11.2f} | "
              f"{f['ag_fade']:>10.2f} / {f['ag_base']:>10.2f} | "
              f"{f['sel_fade']:>7.2f} | {f['speedup_pt']:>10.1f}x")
    print("\nInsercion (us/evento):")
    for f in filas:
        print(f"   n={f['n']:>7}:  FADE {f['ins_fade']:.3f}   "
              f"base(lineal) {f['ins_base']:.3f}")
    return filas


def guardar_plot(filas, ruta="benchmark_plot.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ns = [f["n"] for f in filas]
    pt_fade = [f["pt_fade"] for f in filas]
    pt_base = [f["pt_base"] for f in filas]

    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    ax.plot(ns, pt_fade, "o-", color="#1F4E79", lw=2, label="FADE  ·  O(log n)")
    ax.plot(ns, pt_base, "s--", color="#C55A11", lw=2, label="Linea base lineal (tipo RAP)  ·  O(n)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Numero de eventos  n")
    ax.set_ylabel("Tiempo por consulta PeorTramo (us)")
    ax.set_title("Autoevaluacion: escalabilidad de la consulta PeorTramo")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(ruta, dpi=200)
    print(f"\n[grafico guardado en {ruta}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", action="store_true", help="guardar benchmark_plot.png")
    args = ap.parse_args()

    print("=" * 68)
    print(" AUTOEVALUACION DEL FUNCIONAMIENTO DE FADE")
    print("=" * 68 + "\n")
    autoevaluacion_correccion()
    filas = autoevaluacion_rendimiento()
    if args.plot:
        guardar_plot(filas)
    print("\nFin de la autoevaluacion.")


if __name__ == "__main__":
    main()
