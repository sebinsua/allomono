"""Fit Allo's glyphs to a fixed cell.

A glyph wider than the cell is condensed and a narrower one grown, and each is
drawn from a heavier or lighter weight of Allo so that its stems stay as thick
as its neighbours'. What cannot be treated that way has its own rule: the
letters that are only a stem (letters.py), punctuation, dashes, and symbols,
which keep their proportions.
"""
import unicodedata

from . import outline as O
from .allo import PIXEL, SIZE, preferred
from .letters import specials

# Letters and figures
BEARING = 0.8           # how much of its side bearings a glyph keeps
WIDE_BEARING = 0.6      # and how much the widest keep
MAX_GROW = 1.04         # a letter is never stretched to fill the cell: that distorts the holes inside it
NARROW = 0.72           # glyphs narrower than this share of the cell are not grown
GIVE = 1 / 3            # how much of the room beside a glyph may be spent on putting its stem on a pixel
COMPENSATE = 0.7        # 0: stems scale with the glyph; 1: they keep full thickness
HARD_COMPENSATE = 0.35  # the same, for a glyph condensed to 60%: its counters need the room more
# Letters with three stems or four diagonals get thinner strokes and less margin, as in any monospace.
CROWDED = {"w": 0.5, "M": 0.45, "W": 0.5, "at": 0.5, "ae": 0.3, "oe": 0.3, "AE": 0.3, "OE": 0.3}
STURDY = {"percent": 0.9}   # two small rings and a stroke: left to the usual rule it came out the lightest sign
CROWDED_BEARING = 0.55
ARCHED = {"m"}          # fitted by making the arches smaller whole and the legs longer
ARCHED_BEARING = 0.6
ARCHED_STROKE = 1.0     # its stems, beside its neighbours'
ARCHED_RISE = 1.0       # how tall its arches stay: 1 is Allo's height
ARCHED_COUNTER = 0.13   # the least each of its two counters may be, as a share of the cell
ARCHED_EDGE = 0.02      # and the least clear either side of it
# Capitals and figures stand 18 px tall at 13pt on a Retina display, a little under Allo's own height. In a
# narrow cell they are made narrower than that too: more so than the lowercase.
CAP_SCALE = 18 * PIXEL / (1490 * SIZE)
CAP_HEIGHT_SIGNS = "!?&%#$@£€¥"
ASCENDER = 19 / 18      # ascenders stand 19 px: Allo's, trimmed to the pixel
TALL = "bdfhkl\u00fe"    # the letters with an upright stem above the x-height

# Everything else
PUNCTUATION = 1.2       # points, commas and quotes are this much larger than Allo's
ON_BASELINE, ON_CENTRE, ON_TOP = ".,", ":;·", "'\"`´^*‘’“”°"
DASHES = {"-": None, "−": None, "–": 0.8, "—": 1.0, "_": 1.0}  # share of the cell; None: as wide as the plus
DOLLAR_TIPS = 0.06      # of the cap height, added to each end of the dollar's bar
MARGIN = 0.06           # of the cell, kept clear either side of a symbol
ARROW = 0.82            # a typed arrow's size beside Allo's
SYMBOLS = [  # arrows, keys, shapes and icons; infinity; fractions; per mille, numero and the degree signs
    (0x2190, 0x21FF), (0x2300, 0x23FF), (0x2460, 0x27BF), (0x2B00, 0x2BFF), (0x221E, 0x221E),
    (0xBC, 0xBE), (0x2150, 0x215F), (0x2030, 0x2030), (0x2044, 0x2044), (0x2116, 0x2116), (0x2103, 0x2103), (0x2109, 0x2109),
]  # fmt: skip


def is_symbol(ch):
    return bool(ch) and any(lo <= ord(ch) <= hi for lo, hi in SYMBOLS)


class Fitter:
    """Fits glyphs to the cell. Each result is (shape, advance, scale, dx):
    the outline, its width, and how the original was scaled and moved to get there."""

    def __init__(self, allo, wght, cell, chars):
        self.allo, self.wght, self.cell = allo, wght, cell
        self.chars = chars                       # glyph name -> the character it stands for
        self.special = specials(allo, wght, cell)
        self.squashed = {n for n, ch in chars.items() if unicodedata.category(ch) in ("Lu", "Nd") or ch in CAP_HEIGHT_SIGNS}
        self.cap = O.bounds(allo.shape("H", wght))[3]
        hyphen = O.bounds(allo.shape("hyphen", wght))
        self.bar = hyphen[3] - hyphen[1]             # how thick a level stroke is
        self.done = {}

    def adopt(self, name, base):
        """Treat the glyph `name` as the character `base` stands for: its height, its rules."""
        self.chars[name] = self.chars.get(base, "")
        if base in self.squashed:
            self.squashed.add(name)

    def glyph(self, name):
        if name not in self.done:
            self.done[name] = self._glyph(name)
        return self.done[name]

    def finished(self, name):
        """The glyph as it goes into the font: fitted, and its ascender cut down."""
        shape, advance, scale, dx = self.glyph(name)
        ch = self.chars.get(name, "")
        if ch and unicodedata.normalize("NFD", ch)[0] in TALL:
            x_height, top = self.allo.x_height(self.wght), O.bounds(self.allo.shape("l", self.wght))[3]
            cut = top - ASCENDER * self.cap * CAP_SCALE
            if unicodedata.normalize("NFD", ch)[0] == "f":      # only as much upright stem as f has below its hook
                above = [p[1] for p in O.points(self.allo.shape("f", self.wght)) if p[1] > x_height + 5]
                cut = min(cut, min(above) - x_height - 40)
            if cut > 0:
                shape = O.lower_top(shape, x_height + 30, -cut)
        if advance and shape:
            shape = O.shift(shape, self._to_grid(shape))
        return shape, advance, scale, dx

    def _to_grid(self, shape):
        """How far to move a glyph sideways so that an upright stem starts on a pixel edge (at 13pt on a
        Retina display), which makes that side of it sharp. It is the outer edge of the stem that is placed:
        the left of b, the right of d. Never more than half a pixel, and never more than GIVE of the room
        on the side it moves toward: a letter that fills its cell, like a bold m, stays in the middle of it.
        A glyph with no upright stem stays where it was fitted: a curve or a diagonal is no sharper for
        starting on a pixel, and the move left o, e and v nearer the next letter than the last."""
        tall = 0.25 * self.allo.x_height(self.wght)
        stems = [seg[1][0] for c in shape for seg in c if seg[0] == "L" and abs(seg[1][0] - seg[2][0]) < 0.5 and abs(seg[1][1] - seg[2][1]) > tall]
        if not stems:
            return 0
        b = O.bounds(shape)
        on_right = max(stems) > b[2] - 1 and min(stems) > b[0] + 1
        x = max(stems) if on_right else min(stems)
        move = round(x / PIXEL) * PIXEL - x
        room = self.cell - b[2] if move > 0 else b[0]
        return move if abs(move) <= GIVE * room else 0

    def _glyph(self, name):
        allo, wght = self.allo, self.wght
        if name in self.special:
            shape, dx = self.special[name]
            return self._squash(name, shape), self.cell, 1.0, dx
        if allo.advance(name, wght) == 0:        # a combining mark stays where it is
            return allo.shape(name, wght), 0, 1.0, 0.0
        ch = self.chars.get(name, "")
        if ch == "$":
            return self._dollar(name)
        if ch and ch in ON_BASELINE + ON_CENTRE + ON_TOP:
            return self._punctuation(name, ch)
        if ch in DASHES:
            plus = O.bounds(self._fit("plus")[0])
            return self._level(name, DASHES[ch] * self.cell if DASHES[ch] else plus[2] - plus[0])
        if is_symbol(ch):
            return self._symbol(name)
        if name in ARCHED:
            return self._arched(name)
        return self._accented(name) or self._fit(name)

    # Letters and figures

    def _fit(self, name):
        """Condense or grow the glyph to the cell, from the weight that keeps its stems."""
        allo, cell = self.allo, self.cell
        w, scale = self.wght, 1.0
        for _ in range(4):
            shape, adv = allo.shape(name, w), allo.advance(name, w)
            b = O.bounds(shape)
            if b is None:                        # a space
                return [], cell, 1.0, 0.0
            left, right, ink = b[0], adv - b[2], b[2] - b[0]
            if adv < NARROW * cell:
                scale = 1.0
                break
            over = min(max((adv / cell - 1) / 0.2, 0), 1)
            keep = CROWDED_BEARING if name in CROWDED or name in STURDY else BEARING - (BEARING - WIDE_BEARING) * over
            scale = min(CAP_SCALE if name in self.squashed else MAX_GROW, (cell - keep * max(left + right, 0)) / ink)
            hard = min(max((0.9 - scale) / 0.3, 0), 1)
            k = STURDY.get(name, CROWDED.get(name, COMPENSATE - (COMPENSATE - HARD_COMPENSATE) * hard))
            w = allo.weight_for_stem(allo.stem(self.wght) * scale**-k)
        shape, adv = allo.shape(name, w), allo.advance(name, w)
        b = O.bounds(shape)
        left, right, ink = max(b[0], 0), max(adv - b[2], 0), (b[2] - b[0]) * scale
        share = left / (left + right) if left + right > 0 else 0.5
        share = min(max(share, 0.35), 0.65)
        dx = (cell - ink) * share - b[0] * scale
        dx -= min(b[0] * scale + dx, 0) + max(b[2] * scale + dx - cell, 0)     # an off-centre glyph still stays in its cell
        return self._squash(name, O.transform(shape, lambda p: (p[0] * scale + dx, p[1]))), cell, scale, dx

    def _arched(self, name):
        """m: three stems under two arches, too wide for the cell by a third. It is narrowed, and its
        arches are made a little lower with the straight legs under them longer, so that they spring from
        about where the arches of n and h do. It is drawn from a heavier weight, to keep its strokes, but a
        touch lighter than its neighbours': with half the room inside, full-weight stems make it the
        darkest letter in a word."""
        allo, cell = self.allo, self.cell
        want = ARCHED_STROKE * allo.stem(self.wght)
        w, scale = self.wght, 1.0
        for _ in range(5):
            shape, adv = allo.shape(name, w), allo.advance(name, w)
            b = O.bounds(shape)
            scale = (cell - ARCHED_BEARING * max(b[0] + adv - b[2], 0)) / (b[2] - b[0])
            w = allo.weight_for_stem(want / scale)
        shape = allo.shape(name, w)
        b = O.bounds(shape)
        top = allo.x_height(w)
        # In Bold there is no weight of Allo heavy enough for three stems this close together, so they come
        # out thinner than asked. They are thickened afterwards, as far as leaves the two counters open; and
        # the arches are made lower by whatever share is still missing, or their tops would outweigh the stems.
        most = (cell - 2 * ARCHED_EDGE * cell - 2 * ARCHED_COUNTER * cell) / 3
        final = min(want, max(allo.stem(w) * scale, most))
        rise = ARCHED_RISE * min(1.0, final / want)
        curved = min(p[1] for c in shape for seg in c if seg[0] == "Q" for p in seg[1:] if p[1] > 0.3 * top)
        foot, knee = 0.15 * top, top - (top - curved) * rise      # the legs between them are stretched

        def y(v):
            if v >= curved:
                return top - (top - v) * rise
            return v if v <= foot else foot + (v - foot) * (knee - foot) / (curved - foot)

        dx = (cell - (b[2] - b[0]) * scale) / 2 - b[0] * scale
        shape = O.transform(shape, lambda p: (p[0] * scale + dx, y(p[1])))
        edges = sorted({round(seg[1][0], 1) for c in shape for seg in c if seg[0] == "L" and abs(seg[1][0] - seg[2][0]) < 0.5 and abs(seg[1][1] - seg[2][1]) > 0.25 * top})
        more = (final - (edges[1] - edges[0])) / 2 if len(edges) == 6 else 0
        if more > 0.5:
            # each side of each stem moves out by `more`; what lies between is carried along in proportion
            moved = [e + (-more if i % 2 == 0 else more) for i, e in enumerate(edges)]
            was, now = [-cell] + edges + [2 * cell], [-cell - more] + moved + [2 * cell + more]

            def x(v):
                for i in range(len(was) - 1):
                    if was[i] <= v <= was[i + 1]:
                        return now[i] + (v - was[i]) * (now[i + 1] - now[i]) / (was[i + 1] - was[i])
                return v

            shape = O.transform(shape, lambda p: (x(p[0]), p[1]))
        return shape, cell, scale, dx

    def _squash(self, name, shape):
        if name in self.squashed and CAP_SCALE != 1:
            return O.transform(shape, lambda p: (p[0], p[1] * CAP_SCALE))
        return shape

    def _accented(self, name):
        """A letter and what is attached to it: the letter is fitted once, and its accents follow it.
        None if the glyph is not one, or if what is attached does not fit beside the letter
        (d with a caron, a barred D), in which case the whole is fitted instead."""
        allo, wght = self.allo, self.wght
        comps = allo.components(name, wght)
        if not comps or len(comps) < 2 or not self._is_letter(comps[0][0]) or any(self._is_letter(c[0]) for c in comps[1:]):
            return None
        base_name, base_x, _ = comps[0]
        chosen = preferred(base_name, allo.names)
        base, adv, scale, dx = self.glyph(base_name if chosen == name else chosen)
        shape = list(base)
        for mark, ox, oy in comps[1:]:
            m = O.shift(allo.shape(mark, wght), ox, oy)
            b = O.bounds(m)
            centre = (b[0] + b[2]) / 2
            drop = self.cap * (CAP_SCALE - 1) if base_name in self.squashed and b[1] > self.cap / 2 else 0
            shape += O.turning_like(O.shift(m, (centre - base_x) * scale + dx - centre, drop), base)
        b = O.bounds(shape)
        return (shape, adv, scale, dx) if b[0] >= 0 and b[2] <= self.cell else None

    def _is_letter(self, name):
        ch = self.chars.get(name) or self.chars.get(name.split(".")[0], "")
        return bool(ch) and unicodedata.category(ch)[0] in "LN" and name not in self.allo.marks

    # Everything else

    def _centred(self, shape):
        b = O.bounds(shape)
        dx = (self.cell - (b[2] - b[0])) / 2 - b[0]
        return O.shift(shape, dx), self.cell, 1.0, dx

    def _dollar(self, name):
        """Allo's dollar shows only the two tips of its bar, and at text sizes it reads as an S.
        The tips are made longer, so the sign that starts every shell variable is unmistakable."""
        shape, adv, scale, dx = self._fit(name)
        s = O.bounds(self.glyph("S")[0])
        more = DOLLAR_TIPS * self.cap
        shape = O.transform(shape, lambda p: (p[0], p[1] + more) if p[1] > s[3] + 2 else (p[0], p[1] - more) if p[1] < s[1] - 2 else p)
        return shape, adv, scale, dx

    def _punctuation(self, name, ch):
        shape = self.allo.shape(name, self.wght)
        b = O.bounds(shape)
        y = 0 if ch in ON_BASELINE else b[3] if ch in ON_TOP else (b[1] + b[3]) / 2
        larger = min(PUNCTUATION, 0.94 * self.cell / (b[2] - b[0]))      # a pair of quotes has to stay in its cell
        return self._centred(O.scale(shape, larger, ((b[0] + b[2]) / 2, y)))

    def _level(self, name, width):
        """A level stroke, made `width` long."""
        shape = self.allo.shape(name, self.wght)
        b = O.bounds(shape)
        mid, change = (b[0] + b[2]) / 2, width - (b[2] - b[0])
        if change < 0:
            return self._centred(O.excise(shape, mid + change / 2, mid - change / 2) or O.scale_x(shape, width / (b[2] - b[0]), mid))
        return self._centred(O.stretch(shape, mid, change))

    def _symbol(self, name):
        """A symbol keeps its proportions: a level shaft is shortened, anything else scaled whole."""
        allo, room = self.allo, self.cell * (1 - 2 * MARGIN)
        shape = O.union(allo.shape(name, self.wght))
        b = O.bounds(shape)
        if b[2] - b[0] <= room:
            return self._centred(shape)
        w = self.wght
        for _ in range(3):
            shape = self._shorten(O.union(allo.shape(name, w)), room)
            b = O.bounds(shape)
            s = min(1, room / (b[2] - b[0]))
            w = allo.weight_for_stem(allo.stem(self.wght) * s**-HARD_COMPENSATE)
        return self._centred(O.scale(shape, s, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)))

    def _shorten(self, shape, room):
        """Take the excess out of a level shaft in the middle, if there is one long enough."""
        b = O.bounds(shape)
        excess, span = b[2] - b[0] - room, O.level_span(shape)
        if excess <= 0 or span is None or span[1] - span[0] < excess * 1.15:
            return shape
        mid = (span[0] + span[1]) / 2
        cut = O.excise(shape, mid - excess / 2, mid + excess / 2)
        return shape if cut is None else cut

    def arrow(self, name):
        """One of Allo's arrows drawn across two cells, ending where a single-cell arrow would. It is made
        smaller, as the capitals are, from a weight that keeps its stroke: full size, it shouted."""
        heavier = self.allo.weight_for_stem(self.allo.stem(self.wght) / ARROW)
        shape = O.union(self.allo.shape(name, heavier))
        b = O.bounds(shape)
        shape = O.scale(shape, ARROW, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
        b = O.bounds(shape)
        want, ink = self.cell * (2 - 2 * MARGIN), b[2] - b[0]
        lo, hi = O.level_span(shape)             # the shaft
        mid = (lo + hi) / 2
        if ink < want:
            shape = O.stretch(shape, mid, want - ink)
        elif ink > want:
            shape = O.excise(shape, mid - (ink - want) / 2, mid + (ink - want) / 2) or O.scale_x(shape, want / ink, mid)
        return O.shift(shape, self.cell * (1 - MARGIN) - O.bounds(shape)[2])
