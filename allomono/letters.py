"""The letters too narrow for a cell, widened so that they fill it.

A bare stem takes up a fifth of a cell, and no placing of it hides the rest.
Every monospace answers that the same way: something at the top left of the
stem and something along the bottom. Here it is done with Allo's own parts.
i and l end in the tail Allo gives its tailed l, made a little longer; i has a
short flag in the stroke of Allo's crossbars; and hooks and arms grow as
curves (outline.swell).
"""
from . import outline as O


STEM = 0.13      # how far left of the centre the stems of i and l stand, as a share of the cell
FOOT = 0.24      # how far right of the centre the tails of i and l reach
TAIL = 0.29      # and the tail of t: the same length from its stem, which stands further right
FLAG = 0.17      # the length of the flag on i
BAR = 0.36       # how far the crossbar of t reaches left of the centre


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

    # i and l: the stem stands left of centre and ends in the tail Allo gives its tailed l, a little longer, so it
    # turns toward the next letter without reaching it. i has a short flag as well.
    sc = cx - STEM * cell
    for name, top in (("l.ss02", m.ascender), ("idotless", m.x_height)):
        shape, _ = _place(allo.shape("l.ss02", wght), m.ascender * 0.6, sc)
        shape = O.lower_top(shape, m.x_height / 2, top - m.ascender)
        shape = _grow_right(shape, cx + FOOT * cell, O.level_x(shape, "bottom") + 1)
        if name == "idotless":
            shape.append(O.rounded_rect(sc - v / 2 - FLAG * cell, top - h, sc + v / 2, top, r))
        lo, hi = O.span_at(allo.shape(name, wght), top / 2)
        out[name] = (O.union(shape), sc - (lo + hi) / 2)

    # j: Allo's j, its hook grown
    sc = cx                                  # in the middle: its hook reaches back under the letter before
    shape, was = _place(allo.shape("jdotless", wght), m.x_height / 2, sc)
    shape = _grow_left(shape, sc - v / 2 - 0.27 * cell, O.level_x(shape, "bottom", x_max=sc - v / 2) - 1)
    out["jdotless"] = (O.union(shape), sc - was)

    # f: a wider hook, and the crossbar a little longer to the left
    sc = cx - 0.06 * cell
    shape, was = _place(allo.shape("f", wght), m.x_height * 0.3, sc)
    shape = _grow_right(shape, cx + reach, O.level_x(shape, "top", x_min=sc + v / 2) + 1)
    shape = _grow_left(shape, cx - reach, (O.bounds(shape)[0] + sc - v / 2) / 2)
    out["f"] = (O.union(shape), sc - was)

    # t: a longer tail, and a wide crossbar
    sc = cx - 0.08 * cell
    t = allo.shape("t", wght)
    shape, was = _place(t, m.x_height + 0.5 * (O.bounds(t)[3] - m.x_height), sc)
    shape = _grow_right(shape, cx + TAIL * cell, O.level_x(shape, "bottom", x_min=sc + v / 2) + 1)
    shape = _grow_left(shape, cx - BAR * cell, (O.bounds(shape)[0] + sc - v / 2) / 2)
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
