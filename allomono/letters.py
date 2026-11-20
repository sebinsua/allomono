"""The letters too narrow for a cell, widened in Allo's own voice.

Allo's own narrow letters end in curves: the tail of its t, the hook of its j.
Here i and l end in that hook, turned to face right and set on the baseline,
and where a letter needs more width its curves grow (outline.swell). Nothing is added to the top of a stem: flags and slabs read
as monospace rather than as Allo, and a flick borrowed from Allo's 1 looked
like a snout. These letters are narrow, and are left with air round them.
"""
from . import outline as O


TAIL = 0.27      # how far a tail or hook reaches beyond its stem, as a share of the cell
HOOK = {"l.ss02": 1.9, "idotless": 1.55}   # the hook that ends l, and the quieter one on i, as multiples of the hook on Allo's j


class Measure:
    """Allo's stroke at one weight."""

    def __init__(self, allo, wght):
        l = O.bounds(allo.shape("l", wght))
        hy = O.bounds(allo.shape("hyphen", wght))
        self.stem = l[2] - l[0]
        self.bar = hy[3] - hy[1]
        self.ascender = l[3]
        self.x_height = O.bounds(allo.shape("idotless", wght))[3]
        serif = allo.shape("I.1", wght)
        b = O.bounds(serif)
        level = [p[0] for p in O.points(serif) if abs(p[1] - b[1]) < 0.5]
        self.corner = min(level) - b[0]


def _place(shape, at_y, stem_centre):
    lo, hi = O.span_at(shape, at_y)
    return O.shift(shape, stem_centre - (lo + hi) / 2), (lo + hi) / 2


def _grow_right(shape, target, cut):
    b = O.bounds(shape)
    return O.swell(shape, cut, target - b[2]) if target > b[2] + 1 else shape


def _grow_left(shape, target, cut):
    b = O.bounds(shape)
    return O.swell(shape, cut, target - b[0]) if target < b[0] - 1 else shape


def specials(allo, wght, cell):
    """name -> (shape, dx) where dx is how far the letter's stem moved (accents follow it)."""
    m = Measure(allo, wght)
    cx, v, h, r = cell / 2, m.stem, m.bar, m.corner
    reach = 0.27 * cell                      # how far from the centre these letters extend
    out = {}

    def hooked(top, sc, size):
        """A stem ending in a round, upturned hook: the hook of Allo's j, made larger, turned to face right and
        set on the baseline. It is enlarged whole, from a lighter weight of Allo, so its curve stays round and
        its stroke stays the thickness of the stem: stretching it sideways made a hockey stick."""
        light = allo.weight_for_stem(v / size)
        shape = O.scale(allo.shape("jdotless", light), size, (0, 0))
        lo, hi = O.span_at(shape, m.x_height / 2)
        shape = [O.reverse(c) for c in O.transform(shape, lambda p: (sc + (lo + hi) / 2 - p[0], p[1]))]
        shape = O.shift(shape, 0, O.bounds(allo.shape("o", wght))[1] - O.bounds(shape)[1])   # sits where o sits
        return O.lower_top(shape, m.x_height * 0.8, top - O.bounds(shape)[3])

    # i and l: a stem and its hook, and nothing else, centred in the cell as a whole.
    for name, top in (("l.ss02", m.ascender), ("idotless", m.x_height)):
        shape = hooked(top, cx, HOOK[name])
        b = O.bounds(shape)
        dx = cx - (b[0] + b[2]) / 2
        lo, hi = O.span_at(allo.shape(name, wght), top / 2)
        out[name] = (O.union(O.shift(shape, dx)), cx + dx - (lo + hi) / 2)

    # j: Allo's j, its hook grown to the same length
    sc = cx                                  # in the middle: its hook reaches back under the letter before
    shape, was = _place(allo.shape("jdotless", wght), m.x_height / 2, sc)
    shape = _grow_left(shape, sc - v / 2 - TAIL * cell, O.level_x(shape, "bottom", x_max=sc - v / 2) - 1)
    out["jdotless"] = (O.union(shape), sc - was)

    # f: a wider hook, and the crossbar a little longer to the left
    sc = cx - 0.06 * cell
    shape, was = _place(allo.shape("f", wght), m.x_height * 0.3, sc)
    shape = _grow_right(shape, cx + reach, O.level_x(shape, "top", x_min=sc + v / 2) + 1)
    shape = _grow_left(shape, cx - reach, (O.bounds(shape)[0] + sc - v / 2) / 2)
    out["f"] = (O.union(shape), sc - was)

    # t: a wider tail, and the crossbar a little longer to the left
    sc = cx - 0.08 * cell
    t = allo.shape("t", wght)
    shape, was = _place(t, m.x_height + 0.5 * (O.bounds(t)[3] - m.x_height), sc)
    shape = _grow_right(shape, cx + reach, O.level_x(shape, "bottom", x_min=sc + v / 2) + 1)
    shape = _grow_left(shape, cx - reach, (O.bounds(shape)[0] + sc - v / 2) / 2)
    out["t"] = (O.union(shape), sc - was)

    # r: a wider arm
    sc = cx - 0.15 * cell
    shape, was = _place(allo.shape("r", wght), m.x_height * 0.3, sc)
    shape = _grow_right(shape, cx + reach + 0.05 * cell, O.level_x(shape, "top", x_min=sc + v / 2) - 1)
    out["r"] = (O.union(shape), sc - was)

    # I: Allo's serifed I as drawn; its serifs are short already
    shape = allo.shape("I.1", wght)
    lo, hi = O.span_at(shape, O.bounds(shape)[3] / 2)
    out["I.1"] = (O.shift(shape, cx - (lo + hi) / 2), cx - (lo + hi) / 2)

    # 1: Allo's plain one with a short foot
    sc = cx + 0.04 * cell
    one = allo.shape("one", wght)
    shape, was = _place(one, O.bounds(one)[3] * 0.3, sc)
    shape.append(O.rounded_rect(sc - 0.2 * cell, 0, sc + 0.2 * cell, h, r))
    out["one.foot"] = (O.union(shape), sc - was)
    return out
