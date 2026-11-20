"""Allo, the font allomono is made from: its letters at any weight, as outlines.

Allo is read from its variable font (fetched by fetch.py), at its text
optical size and the roundness of its static fonts.
"""
from bisect import bisect_left
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.ttLib import TTFont

from . import outline as O

ROOT = Path(__file__).resolve().parent.parent
ALLO = ROOT / "upstream/allo/fonts/variable/AlloVariable.ttf"

OPSZ = 14   # Allo's text design: a tall x-height and letters already a little narrow, as a small size wants
ROND = 50   # the roundness of Allo's static fonts, and of its own site
# Allo is set at the size that puts its x-height on a whole pixel (14) at 13pt on a Retina display, so the
# tops of the lowercase are sharp.
PIXEL = 2048 / 26
SIZE = 14 * PIXEL / 1118


def preferred(name, have):
    """Allo's disambiguated forms (footed 1, slashed zero, tailed l, serifed I) are allomono's defaults."""
    if name == "one":
        return "one.foot"
    if name == "zero":
        return "zero.slash"
    if name + ".ss02" in have:
        return name + ".ss02"
    if name.startswith("I") and name + ".1" in have:
        return name + ".1"
    return name


class Allo:
    def __init__(self, path=ALLO, rond=None):
        self.font = TTFont(path)
        self.rond = ROND if rond is None else rond
        self.names = set(self.font.getGlyphOrder())
        self.marks = {n for n, c in self.font["GDEF"].table.GlyphClassDef.classDefs.items() if c == 3}
        self._sets, self._shapes = {}, {}
        self._stems = [(w, self._stem(w)) for w in range(100, 901, 50)]

    def glyphs(self, wght):
        wght = round(wght)
        if wght not in self._sets:
            self._sets[wght] = self.font.getGlyphSet(location={"wght": wght, "opsz": OPSZ, "ROND": self.rond})
        return self._sets[wght]

    def shape(self, name, wght):
        """The glyph's outline at a weight, with anything it is composed of drawn in."""
        key = (name, round(wght))
        if key not in self._shapes:
            gs = self.glyphs(wght)
            rec = DecomposingRecordingPen(gs)
            gs[name].draw(rec)
            self._shapes[key] = O.transform(O.from_recording(rec.value), lambda p: (p[0] * SIZE, p[1] * SIZE))
        return self._shapes[key]

    def components(self, name, wght):
        """(name, x, y) for each part of a glyph composed of others, or None for one drawn directly."""
        gs = self.glyphs(wght)
        rec = RecordingPen()
        gs[name].draw(rec)
        if rec.value and all(op == "addComponent" for op, _ in rec.value):
            assert all(args[1][:4] == (1, 0, 0, 1) for _, args in rec.value), f"{name}: a component is scaled or turned, which the fitting does not carry over"
            return [(args[0], args[1][4] * SIZE, args[1][5] * SIZE) for _, args in rec.value]
        return None

    def x_height(self, wght):
        return bounds_top(self.shape("x", wght))

    def advance(self, name, wght):
        return self.glyphs(wght)[name].width * SIZE

    def _stem(self, wght):
        b = O.bounds(self.shape("l", wght))
        return b[2] - b[0]

    def stem(self, wght):
        """How thick an upright stroke is at a weight."""
        return _interpolate(self._stems, wght)

    def weight_for_stem(self, stem):
        """The weight at which an upright stroke is this thick."""
        return _interpolate([(s, w) for w, s in self._stems], stem)


def bounds_top(shape):
    return O.bounds(shape)[3]


def _interpolate(table, x):
    xs = [a for a, _ in table]
    if x <= xs[0]:
        return table[0][1]
    if x >= xs[-1]:
        return table[-1][1]
    i = bisect_left(xs, x)
    (x0, y0), (x1, y1) = table[i - 1], table[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
