"""
FADE — Feedback Augmented Dynamic Event tree
============================================

Implementacion de referencia del Proyecto 1 (MCC6, Analisis y Diseno de
Algoritmos). FADE es un arbol de busqueda binario balanceado (base
rojo-negro) indexado por la marca de tiempo del evento y AUMENTADO en cada
nodo con:

  * tam            : numero de eventos del subarbol   (estadistica de orden)
  * sum, mn, mx    : agregados de una metrica escalar  (val) del subarbol
  * W, P, S, B     : campos de "peor tramo contiguo" sobre el peso de
                     severidad (w) del subarbol -> patron de maxima
                     subsecuencia contigua (Kadane) hecho combinable.

Reglas de combinacion (asociativas, O(1)); para A a la izquierda de B:
  tam = A.tam + B.tam
  sum = A.sum + B.sum ; mn = min(A.mn,B.mn) ; mx = max(A.mx,B.mx)
  W   = A.W + B.W
  P   = max(A.P , A.W + B.P)
  S   = max(B.S , B.W + A.S)
  B   = max(A.B , B.B , A.S + B.P)

El tramo vacio esta permitido (severidad 0), por lo que P,S,B >= 0.

Este archivo es autonomo y NO requiere librerias externas. Ejecutarlo
lanza una bateria de pruebas aleatorias contra un verificador de fuerza
bruta (ver la funcion main() al final).
"""

from dataclasses import dataclass, field
from typing import Optional
import math
import random

RED, BLACK = 0, 1
NEG_INF = -math.inf
POS_INF = math.inf


# --------------------------------------------------------------------------
# Elemento monoide: el resumen aumentado de un conjunto de eventos contiguos.
# --------------------------------------------------------------------------
@dataclass
class Elem:
    tam: int = 0
    sum: float = 0.0
    mn: float = POS_INF
    mx: float = NEG_INF
    W: float = 0.0
    P: float = 0.0
    S: float = 0.0
    B: float = 0.0


IDENT = Elem()  # elemento neutro (conjunto vacio)


def combine(a: Elem, b: Elem) -> Elem:
    """Combina el resumen de A (izquierda, mas antiguo) con el de B (derecha)."""
    return Elem(
        tam=a.tam + b.tam,
        sum=a.sum + b.sum,
        mn=min(a.mn, b.mn),
        mx=max(a.mx, b.mx),
        W=a.W + b.W,
        P=max(a.P, a.W + b.P),
        S=max(b.S, b.W + a.S),
        B=max(a.B, b.B, a.S + b.P),
    )


def combine3(a: Elem, b: Elem, c: Elem) -> Elem:
    return combine(combine(a, b), c)


# --------------------------------------------------------------------------
# Nodo del arbol.
# --------------------------------------------------------------------------
class Node:
    __slots__ = ("t", "val", "w", "color", "left", "right", "parent",
                 "tam", "sum", "mn", "mx", "W", "P", "S", "B")

    def __init__(self, t: float, val: float, w: float):
        self.t = t          # marca de tiempo (clave)
        self.val = val      # valor de la metrica escalar de ejemplo
        self.w = w          # peso de severidad
        self.color = RED
        self.left = None
        self.right = None
        self.parent = None
        # atributos aumentados (se recalculan con recompute)
        self.tam = 1
        self.sum = val
        self.mn = val
        self.mx = val
        self.W = w
        self.P = max(0.0, w)
        self.S = max(0.0, w)
        self.B = max(0.0, w)

    def elem(self) -> Elem:
        """Resumen aumentado de TODO el subarbol enraizado en este nodo."""
        return Elem(self.tam, self.sum, self.mn, self.mx,
                    self.W, self.P, self.S, self.B)


def _elem(node: Optional[Node]) -> Elem:
    return node.elem() if node is not None else IDENT


def _singleton(node: Node) -> Elem:
    return Elem(1, node.val, node.val, node.val,
                node.w, max(0.0, node.w), max(0.0, node.w), max(0.0, node.w))


# --------------------------------------------------------------------------
# FADE: arbol rojo-negro aumentado.
# --------------------------------------------------------------------------
class Fade:
    def __init__(self):
        self.root: Optional[Node] = None

    # ---- mantenimiento de la aumentacion (O(1) por nodo) -----------------
    @staticmethod
    def recompute(x: Node) -> None:
        L, R = _elem(x.left), _elem(x.right)
        mid = _singleton(x)
        e = combine3(L, mid, R)
        x.tam, x.sum, x.mn, x.mx = e.tam, e.sum, e.mn, e.mx
        x.W, x.P, x.S, x.B = e.W, e.P, e.S, e.B

    def _recompute_up(self, x: Optional[Node]) -> None:
        while x is not None:
            self.recompute(x)
            x = x.parent

    # ---- rotaciones (recalculan la aumentacion de abajo hacia arriba) ----
    def _left_rotate(self, x: Node) -> None:
        y = x.right
        x.right = y.left
        if y.left is not None:
            y.left.parent = x
        y.parent = x.parent
        if x.parent is None:
            self.root = y
        elif x is x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y
        self.recompute(x)   # primero el hijo
        self.recompute(y)   # luego el padre

    def _right_rotate(self, x: Node) -> None:
        y = x.left
        x.left = y.right
        if y.right is not None:
            y.right.parent = x
        y.parent = x.parent
        if x.parent is None:
            self.root = y
        elif x is x.parent.right:
            x.parent.right = y
        else:
            x.parent.left = y
        y.right = x
        x.parent = y
        self.recompute(x)
        self.recompute(y)

    # ---- INSERTAR --------------------------------------------------------
    def insert(self, t: float, val: float, w: float) -> None:
        z = Node(t, val, w)
        y = None
        x = self.root
        while x is not None:
            y = x
            if z.t < x.t:
                x = x.left
            elif z.t > x.t:
                x = x.right
            else:               # clave existente -> comportarse como actualizar
                x.val, x.w = val, w
                self._recompute_up(x)
                return
        z.parent = y
        if y is None:
            self.root = z
        elif z.t < y.t:
            y.left = z
        else:
            y.right = z
        self._recompute_up(z)          # aumentacion antes de reequilibrar
        self._insert_fixup(z)

    def _insert_fixup(self, z: Node) -> None:
        while z.parent is not None and z.parent.color == RED:
            if z.parent is z.parent.parent.left:
                u = z.parent.parent.right
                if u is not None and u.color == RED:
                    z.parent.color = BLACK
                    u.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.right:
                        z = z.parent
                        self._left_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._right_rotate(z.parent.parent)
            else:
                u = z.parent.parent.left
                if u is not None and u.color == RED:
                    z.parent.color = BLACK
                    u.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.left:
                        z = z.parent
                        self._right_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._left_rotate(z.parent.parent)
        self.root.color = BLACK

    # ---- ELIMINAR --------------------------------------------------------
    def _find(self, t: float) -> Optional[Node]:
        x = self.root
        while x is not None and x.t != t:
            x = x.left if t < x.t else x.right
        return x

    @staticmethod
    def _minimum(x: Node) -> Node:
        while x.left is not None:
            x = x.left
        return x

    def _transplant(self, u: Node, v: Optional[Node]) -> None:
        if u.parent is None:
            self.root = v
        elif u is u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        if v is not None:
            v.parent = u.parent

    def delete(self, t: float) -> bool:
        z = self._find(t)
        if z is None:
            return False
        y = z
        y_orig_color = y.color
        # x = nodo que ocupa la posicion; x_parent para el fixup con None
        if z.left is None:
            x, x_parent = z.right, z.parent
            self._transplant(z, z.right)
        elif z.right is None:
            x, x_parent = z.left, z.parent
            self._transplant(z, z.left)
        else:
            y = self._minimum(z.right)
            y_orig_color = y.color
            x = y.right
            if y.parent is z:
                x_parent = y
            else:
                x_parent = y.parent
                self._transplant(y, y.right)
                y.right = z.right
                y.right.parent = y
            self._transplant(z, y)
            y.left = z.left
            y.left.parent = y
            y.color = z.color
        # recalcular aumentacion desde el nodo mas profundo afectado hacia arriba
        self._recompute_up(x_parent)
        if y_orig_color == BLACK:
            self._delete_fixup(x, x_parent)
        return True

    def _delete_fixup(self, x: Optional[Node], parent: Optional[Node]) -> None:
        # x puede ser None (hoja negra ficticia); usamos 'parent' explicito.
        while x is not self.root and (x is None or x.color == BLACK):
            if x is (parent.left if parent else None):
                w = parent.right
                if w is not None and w.color == RED:
                    w.color = BLACK
                    parent.color = RED
                    self._left_rotate(parent)
                    w = parent.right
                if (w is None or
                        ((w.left is None or w.left.color == BLACK) and
                         (w.right is None or w.right.color == BLACK))):
                    if w is not None:
                        w.color = RED
                    x, parent = parent, parent.parent
                else:
                    if w.right is None or w.right.color == BLACK:
                        if w.left is not None:
                            w.left.color = BLACK
                        w.color = RED
                        self._right_rotate(w)
                        w = parent.right
                    w.color = parent.color
                    parent.color = BLACK
                    if w.right is not None:
                        w.right.color = BLACK
                    self._left_rotate(parent)
                    x = self.root
            else:
                w = parent.left
                if w is not None and w.color == RED:
                    w.color = BLACK
                    parent.color = RED
                    self._right_rotate(parent)
                    w = parent.left
                if (w is None or
                        ((w.right is None or w.right.color == BLACK) and
                         (w.left is None or w.left.color == BLACK))):
                    if w is not None:
                        w.color = RED
                    x, parent = parent, parent.parent
                else:
                    if w.left is None or w.left.color == BLACK:
                        if w.right is not None:
                            w.right.color = BLACK
                        w.color = RED
                        self._left_rotate(w)
                        w = parent.left
                    w.color = parent.color
                    parent.color = BLACK
                    if w.left is not None:
                        w.left.color = BLACK
                    self._right_rotate(parent)
                    x = self.root
        if x is not None:
            x.color = BLACK

    # ---- ACTUALIZAR ------------------------------------------------------
    def update(self, t: float, val: float, w: float) -> bool:
        x = self._find(t)
        if x is None:
            return False
        x.val, x.w = val, w
        self._recompute_up(x)
        return True

    # ---- ORDEN POR TIEMPO (estadistica de orden): k-esimo, 1-indexado ----
    def select(self, k: int) -> Optional[Node]:
        x = self.root
        while x is not None:
            left = x.left.tam if x.left else 0
            if k == left + 1:
                return x
            elif k <= left:
                x = x.left
            else:
                k -= left + 1
                x = x.right
        return None

    # ---- CONSULTAS DE RANGO ---------------------------------------------
    def _query_suffix(self, node: Optional[Node], a: float) -> Elem:
        """Resumen de los eventos con clave >= a en el subarbol 'node'."""
        if node is None:
            return IDENT
        if node.t < a:
            return self._query_suffix(node.right, a)
        # node.t >= a: sufijo del izquierdo + node + TODO el derecho
        return combine3(self._query_suffix(node.left, a),
                        _singleton(node),
                        _elem(node.right))

    def _query_prefix(self, node: Optional[Node], b: float) -> Elem:
        """Resumen de los eventos con clave <= b en el subarbol 'node'."""
        if node is None:
            return IDENT
        if node.t > b:
            return self._query_prefix(node.left, b)
        return combine3(_elem(node.left),
                        _singleton(node),
                        self._query_prefix(node.right, b))

    def query_range(self, a: float, b: float) -> Elem:
        """Resumen aumentado de los eventos con a <= clave <= b (O(log n))."""
        node = self.root
        while node is not None:
            if b < node.t:
                node = node.left
            elif a > node.t:
                node = node.right
            else:
                left = self._query_suffix(node.left, a)
                right = self._query_prefix(node.right, b)
                return combine3(left, _singleton(node), right)
        return IDENT

    # ---- API de alto nivel del Problema 2.1 ------------------------------
    def agregado(self, a: float, b: float, op: str) -> float:
        e = self.query_range(a, b)
        if op == "cuenta":
            return e.tam
        if op == "suma":
            return e.sum
        if op == "media":
            return e.sum / e.tam if e.tam else 0.0
        if op == "min":
            return e.mn
        if op == "max":
            return e.mx
        raise ValueError(op)

    def peor_tramo(self, a: float, b: float) -> float:
        """Severidad maxima de un tramo contiguo dentro de [a,b]."""
        return self.query_range(a, b).B

    # ---- utilidades de verificacion (comprobaciones) ---------------------
    def check_rb(self) -> int:
        """Verifica invariantes rojo-negro. Devuelve la altura negra."""
        if self.root is not None:
            assert self.root.color == BLACK, "la raiz debe ser negra"

        def bh(x):
            if x is None:
                return 1  # las hojas nil son negras
            if x.color == RED:
                assert (x.left is None or x.left.color == BLACK) and \
                       (x.right is None or x.right.color == BLACK), \
                       "un nodo rojo no puede tener hijo rojo"
            lh, rh = bh(x.left), bh(x.right)
            assert lh == rh, "alturas negras desiguales"
            return lh + (1 if x.color == BLACK else 0)

        return bh(self.root)

    def check_augment(self) -> None:
        """Verifica que cada atributo aumentado coincide con recomputarlo."""
        def chk(x):
            if x is None:
                return
            chk(x.left); chk(x.right)
            L, R = _elem(x.left), _elem(x.right)
            e = combine3(L, _singleton(x), R)
            assert x.tam == e.tam, "tam inconsistente"
            assert math.isclose(x.W, e.W), "W inconsistente"
            assert math.isclose(x.P, e.P), "P inconsistente"
            assert math.isclose(x.S, e.S), "S inconsistente"
            assert math.isclose(x.B, e.B), "B inconsistente"
        chk(self.root)

    def inorder(self):
        out = []
        def go(x):
            if x is None:
                return
            go(x.left); out.append((x.t, x.val, x.w)); go(x.right)
        go(self.root)
        return out


# --------------------------------------------------------------------------
# Verificador de fuerza bruta (referencia lenta pero obviamente correcta).
# --------------------------------------------------------------------------
def brute_peor_tramo(events, a, b):
    ws = [w for (t, v, w) in sorted(events) if a <= t <= b]
    best = 0.0  # tramo vacio permitido
    for i in range(len(ws)):
        acc = 0.0
        for j in range(i, len(ws)):
            acc += ws[j]
            best = max(best, acc)
    return best


def brute_agregado(events, a, b, op):
    vs = [v for (t, v, w) in sorted(events) if a <= t <= b]
    if op == "cuenta":
        return len(vs)
    if op == "suma":
        return sum(vs)
    if op == "media":
        return sum(vs) / len(vs) if vs else 0.0
    if op == "min":
        return min(vs) if vs else POS_INF
    if op == "max":
        return max(vs) if vs else NEG_INF


def brute_select(events, k):
    s = sorted(events)
    return s[k - 1] if 1 <= k <= len(s) else None


# --------------------------------------------------------------------------
# Pruebas.
# --------------------------------------------------------------------------
def test_worked_example():
    """Ejemplo del documento: pesos [-1,3,-2,4,2,-5,1] -> B = 7 (e2..e5)."""
    tree = Fade()
    weights = [-1, 3, -2, 4, 2, -5, 1]
    for i, w in enumerate(weights, start=1):
        tree.insert(t=i, val=w, w=w)
    tree.check_rb()
    tree.check_augment()
    b = tree.peor_tramo(1, 7)
    assert b == 7, f"esperado 7, obtenido {b}"
    print(f"[ok] ejemplo trabajado: peor tramo global = {b} (tramo e2..e5)")


def test_random(seed=0, rounds=300, universe=60):
    rng = random.Random(seed)
    tree = Fade()
    present = {}  # t -> (val, w)
    for _ in range(rounds):
        op = rng.random()
        if op < 0.5 or not present:          # insertar / actualizar
            t = rng.randrange(universe)
            val = rng.randint(-9, 9)
            w = rng.randint(-9, 9)
            tree.insert(t, val, w)
            present[t] = (val, w)
        elif op < 0.65:                       # eliminar
            t = rng.choice(list(present))
            tree.delete(t)
            del present[t]
        else:                                 # consulta aleatoria
            a = rng.randrange(universe)
            b = rng.randrange(universe)
            if a > b:
                a, b = b, a
            ev = [(t, v, w) for t, (v, w) in present.items()]
            assert math.isclose(tree.peor_tramo(a, b),
                                brute_peor_tramo(ev, a, b))
            for opn in ("cuenta", "suma", "min", "max"):
                got = tree.agregado(a, b, opn)
                exp = brute_agregado(ev, a, b, opn)
                assert math.isclose(got, exp), (opn, got, exp)
            if present:
                k = rng.randint(1, len(present))
                got = tree.select(k)
                exp = brute_select(ev, k)
                assert got.t == exp[0]
        # invariantes tras CADA operacion
        tree.check_rb()
        tree.check_augment()
    print(f"[ok] pruebas aleatorias (seed={seed}, {rounds} operaciones): "
          f"invariantes rojo-negro y aumentacion correctos en todo momento")


def test_height_bound(n=100000):
    """Comprobacion empirica de la cota de altura h <= 2 log2(n+1)."""
    tree = Fade()
    rng = random.Random(1)
    for i in range(n):
        tree.insert(rng.random(), rng.randint(-5, 5), rng.randint(-5, 5))

    def height(x):
        return 0 if x is None else 1 + max(height(x.left), height(x.right))

    import sys
    sys.setrecursionlimit(1 << 20)
    h = height(tree.root)
    bound = 2 * math.log2(n + 1)
    tree.check_rb()
    assert h <= bound, (h, bound)
    print(f"[ok] cota de altura: n={n}, altura real={h}, "
          f"cota teorica 2*log2(n+1)={bound:.1f}")


def main():
    print("== Comprobaciones de FADE ==")
    test_worked_example()
    for s in range(5):
        test_random(seed=s)
    test_height_bound()
    print("\nTodas las comprobaciones pasaron correctamente.")


if __name__ == "__main__":
    main()
