"""Box drawing, blocks and braille, which Allo does not have.

These are drawn here rather than fitted, in Allo's manner: lines the weight of
its strokes, soft outer corners and round ends where a line stops, true arcs
for the rounded corners, and bars whose growing end is rounded: the lower
eighths a sparkline is made of and the left eighths of a progress bar. The
full block, the upper and right halves and the quadrants stay square. Every line runs to the edge of the cell and a
little past it, so boxes join up whatever a terminal does with rounding.
"""
import math
import unicodedata

from . import outline as O
from .allo import PIXEL

LIGHT = 0.85      # a light line's thickness, as a share of Allo's crossbar
HEAVY = 2.0       # a heavy line, as a multiple of a light one
APART = 1.0       # the two lines of a double sit this many light thicknesses either side of centre
SOFT = 0.45       # corner radius of a line's end, as a share of its thickness
OVER_X, OVER_Y = 0.02, 0.02   # how far lines run past the cell, as a share of the cell and of the em
BAR = 0.2         # corner radius of the growing end of a bar, as a share of the cell
DOT = 0.11        # a braille dot's radius, as a share of the cell

UP, RIGHT, DOWN, LEFT = "up", "right", "down", "left"
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}
ACROSS = {UP: (LEFT, RIGHT), DOWN: (LEFT, RIGHT), LEFT: (UP, DOWN), RIGHT: (UP, DOWN)}
WORDS = {"UP": [UP], "DOWN": [DOWN], "LEFT": [LEFT], "RIGHT": [RIGHT], "VERTICAL": [UP, DOWN], "HORIZONTAL": [LEFT, RIGHT]}
WEIGHTS = {"LIGHT": "light", "SINGLE": "light", "HEAVY": "heavy", "DOUBLE": "double"}


class Cell:
    """The box a terminal gives each character, and the lines that fit it.

    Everything is in whole pixels at 13pt on a Retina display, where the cell is 16 by 32 with the
    baseline 6 up: lines are a whole number of pixels thick and start on pixel edges, so they are sharp."""

    def __init__(self, width, bar):
        self.w, self.top, self.bottom = width, 26 * PIXEL, -6 * PIXEL
        self.t = max(1, round(bar * LIGHT / PIXEL)) * PIXEL
        odd = round(self.t / PIXEL) % 2 * PIXEL / 2          # an odd thickness sits half a pixel off centre
        self.cx, self.cy = round(width / 2 / PIXEL) * PIXEL + odd, 10 * PIXEL + odd
        self.ox, self.oy = width * OVER_X, 2048 * OVER_Y
        self.dot = width * DOT * (bar / 200) ** 0.5

    # lines meeting at the centre

    def thickness(self, weight):
        return {"light": self.t, "heavy": self.t * HEAVY, "double": self.t * (2 * APART + 1)}[weight]

    def _arm(self, direction, half, start, soft):
        """A bar from the cell's edge to `start` units short of (or, negative, past) the centre."""
        r = soft * 2 * half * SOFT
        if direction == RIGHT:
            return O.rounded_rect(self.cx + start, self.cy - half, self.w + self.ox, self.cy + half, (r, 0, 0, r))
        if direction == LEFT:
            return O.rounded_rect(-self.ox, self.cy - half, self.cx - start, self.cy + half, (0, r, r, 0))
        if direction == UP:
            return O.rounded_rect(self.cx - half, self.cy + start, self.cx + half, self.top + self.oy, (r, r, 0, 0))
        return O.rounded_rect(self.cx - half, self.bottom - self.oy, self.cx + half, self.cy - start, (0, 0, r, r))

    def lines(self, arms):
        """arms: direction -> "light", "heavy" or "double"."""
        t, gap = self.t, self.t * APART
        plain = "double" not in arms.values()          # doubles keep square corners, so their pairs of lines meet cleanly
        solid, hollow, single = [], [], []
        for d, weight in arms.items():
            across = [arms[p] for p in ACROSS[d] if p in arms]
            widest = max((self.thickness(a) for a in across), default=0)
            opposite = arms.get(OPPOSITE[d])
            soft = 0
            if opposite:
                start = 0
                if plain and self.thickness(weight) > self.thickness(opposite):
                    start, soft = -self.thickness(weight) * SOFT, 1
            elif len(across) == 1:                     # a corner: reach the far side of the line it turns into
                start, soft = -widest / 2, 1 if plain else 0
            elif len(across) == 2:                     # a branch off a line running through
                start = gap - t / 2 if "double" in across and weight != "double" else 0
            else:                                      # a line that simply stops
                start, soft = 0, 1
            if weight != "double":
                single.append(self._arm(d, self.thickness(weight) / 2, start, soft))
                continue
            solid.append(self._arm(d, self.thickness("double") / 2, start, 0))
            if opposite:
                inner = -1
            elif len(across) == 1:
                inner = start + t
            elif len(across) == 2:
                inner = -(gap - t / 2) if "double" in across else self.thickness(across[0]) / 2
            else:
                inner = 0
            hollow.append(self._arm(d, gap - t / 2, inner, 0))
        shape = O.subtract(O.union(solid), O.union(hollow)) if solid else []
        return O.union(shape + single)

    def arc(self, vertical, horizontal):
        """A rounded corner: a quarter circle from the middle of one edge to the middle of another."""
        t, r = self.t, self.w / 2
        sx, sy = (1 if horizontal == RIGHT else -1), (1 if vertical == UP else -1)
        centre = (self.cx + sx * r, self.cy + sy * r)

        def sweep(radius, n=6):
            pts = []
            for i in range(n + 1):
                a = math.pi / 2 * i / n
                pts.append((radius * math.cos(a), radius * math.sin(a), a))
            return pts

        def point(radius, a):                          # the quarter that faces the cell's centre
            return (centre[0] - sx * radius * math.cos(a), centre[1] - sy * radius * math.sin(a))

        def curve(radius, angles):
            segs = []
            for a0, a1 in zip(angles, angles[1:]):
                am = (a0 + a1) / 2
                segs.append(("Q", point(radius, a0), point(radius / math.cos((a1 - a0) / 2), am), point(radius, a1)))
            return segs

        angles = [math.pi / 2 * i / 6 for i in range(7)]
        outer, inner = curve(r + t / 2, angles), curve(r - t / 2, angles[::-1])
        ring = outer + [("L", outer[-1][3], inner[0][1])] + inner + [("L", inner[-1][3], outer[0][1])]
        # the straight runs out to the two edges
        y0, y1 = (centre[1], self.top + self.oy) if vertical == UP else (self.bottom - self.oy, centre[1])
        x0, x1 = (centre[0], self.w + self.ox) if horizontal == RIGHT else (-self.ox, centre[0])
        return O.union([O.clockwise(ring), O.rounded_rect(self.cx - t / 2, y0, self.cx + t / 2, y1, 0), O.rounded_rect(x0, self.cy - t / 2, x1, self.cy + t / 2, 0)])

    def dashes(self, count, weight, upright):
        half = self.thickness(weight) / 2
        r = half * 2 * SOFT
        lo, hi = (self.bottom, self.top) if upright else (0, self.w)
        step = (hi - lo) / count
        out = []
        for i in range(count):
            a, b = lo + (i + 0.2) * step, lo + (i + 0.8) * step
            out.append(O.rounded_rect(self.cx - half, a, self.cx + half, b, r) if upright else O.rounded_rect(a, self.cy - half, b, self.cy + half, r))
        return out

    def diagonal(self, rising):
        (x0, y0), (x1, y1) = ((0, self.bottom), (self.w, self.top)) if rising else ((0, self.top), (self.w, self.bottom))
        length = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / length * self.t / 2, (x1 - x0) / length * self.t / 2
        pts = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
        return O.clockwise([("L", a, b) for a, b in zip(pts, pts[1:] + pts[:1])])

    # blocks

    def block(self, x0, y0, x1, y1, soft=()):
        """A filled part of the cell, in eighths: (0, 0) is its bottom left and (8, 8) its top right.
        `soft` names the corners to round: "top" (or only "top left" or "top right") for a bar that grows
        upward, "right" for one that grows across."""
        height = self.top - self.bottom
        xa = -self.ox if x0 == 0 else self.w * x0 / 8
        xb = self.w + self.ox if x1 == 8 else self.w * x1 / 8
        ya = self.bottom - self.oy if y0 == 0 else self.bottom + height * y0 / 8
        yb = self.top + self.oy if y1 == 8 else self.bottom + height * y1 / 8
        r = min(self.w * BAR, (yb - ya) / 2, (xb - xa) / 2)
        radii = {"top": (0, 0, r, r), "top left": (0, 0, 0, r), "top right": (0, 0, r, 0), "right": (0, r, r, 0)}.get(soft, 0)
        return O.rounded_rect(xa, ya, xb, yb, radii)

    def shade(self, level):
        """A tint: a regular pattern of small squares covering a quarter, a half or three quarters of the cell."""
        cols, rows = 8, 16
        height = self.top - self.bottom
        out = []
        for row in range(rows):
            for col in range(cols):
                light = row % 2 == 0 and (col + row // 2) % 2 == 0
                on = light if level == 1 else (col + row) % 2 == 0 if level == 2 else not (row % 2 == 1 and (col + row // 2) % 2 == 0)
                if on:
                    out.append(O.rounded_rect(self.w * col / cols, self.bottom + height * row / rows, self.w * (col + 1) / cols, self.bottom + height * (row + 1) / rows, 0))
        return O.union(out)

    def powerline(self):
        """The separators shell prompts are built from: solid and outlined arrows, and their round cousins."""
        t, lo, hi, w = self.t, self.bottom - self.oy, self.top + self.oy, self.w

        def flip(shape):
            return [O.reverse(c) for c in O.transform(shape, lambda p: (w - p[0], p[1]))]

        def poly(pts):
            return O.clockwise([("L", a, b) for a, b in zip(pts, pts[1:] + pts[:1])])

        solid = [poly([(-self.ox, lo), (w, self.cy), (-self.ox, hi)])]
        thin = [poly([(-self.ox, lo), (w, self.cy), (-self.ox, hi), (-self.ox, hi - t * 1.6), (w - t * 1.3, self.cy), (-self.ox, lo + t * 1.6)])]
        r = (hi - lo) / 2
        half = [O.rounded_rect(-w, lo, w, hi, r)]             # a pill; its left half lies in the cell before
        half = O.subtract(O.union(half), [O.rounded_rect(-2 * w, lo - 10, -self.ox, hi + 10, 0)])
        return {0xE0B0: solid, 0xE0B1: thin, 0xE0B2: flip(solid), 0xE0B3: flip(thin), 0xE0B4: half, 0xE0B6: flip(half)}

    def braille(self, bits):
        height = self.top - self.bottom
        xs = (self.w * 0.28, self.w * 0.72)
        ys = [self.cy + height * 0.19 * k for k in (1.5, 0.5, -0.5, -1.5)]
        where = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3)]    # dots 1 to 8
        r = self.dot
        return [O.rounded_rect(xs[c] - r, ys[w] - r, xs[c] + r, ys[w] + r, r) for i, (c, w) in enumerate(where) if bits >> i & 1]


def _arms(words):
    """Read a Unicode box drawing name: "DOWN LIGHT AND RIGHT HEAVY", "DOUBLE VERTICAL AND HORIZONTAL"..."""
    words = [w for w in words if w != "AND"]
    arms, pending, weight = {}, [], None
    leading = words[0] in WEIGHTS                     # the weight comes before its directions, or after them
    for word in words:
        if word in WEIGHTS:
            weight = WEIGHTS[word]
            if not leading:
                for d in pending:
                    arms[d] = weight
                pending = []
        elif word in WORDS:
            if leading:
                for d in WORDS[word]:
                    arms[d] = weight
            else:
                pending += WORDS[word]
        else:
            return None
    return arms if arms and not pending else None


QUADRANTS = {
    0x2596: ["ll"], 0x2597: ["lr"], 0x2598: ["ul"], 0x2599: ["ul", "ll", "lr"], 0x259A: ["ul", "lr"], 0x259B: ["ul", "ur", "ll"],
    0x259C: ["ul", "ur", "lr"], 0x259D: ["ur"], 0x259E: ["ur", "ll"], 0x259F: ["ur", "ll", "lr"],
}  # fmt: skip
QUARTER = {"ll": (0, 0, 4, 4), "lr": (4, 0, 8, 4), "ul": (0, 4, 4, 8), "ur": (4, 4, 8, 8)}


def drawn(cell):
    """codepoint -> outline, for every character drawn here."""
    out = {}
    for cp in range(0x2500, 0x2580):
        words = unicodedata.name(chr(cp)).replace("BOX DRAWINGS ", "").split()
        if "DASH" in words:
            count = {"DOUBLE": 2, "TRIPLE": 3, "QUADRUPLE": 4}[words[1]]
            out[cp] = cell.dashes(count, WEIGHTS[words[0]], words[-1] == "VERTICAL")
        elif "ARC" in words:
            out[cp] = cell.arc(UP if "UP" in words else DOWN, RIGHT if "RIGHT" in words else LEFT)
        elif "DIAGONAL" in words:
            out[cp] = [cell.diagonal(True)] * ("CROSS" in words or words[2:4] == ["UPPER", "RIGHT"]) + [cell.diagonal(False)] * ("CROSS" in words or words[2:4] == ["UPPER", "LEFT"])
        else:
            out[cp] = cell.lines(_arms(words))
    out[0x23BF] = cell.lines({UP: "light", RIGHT: "light"})     # the corner that tools draw under a line of output
    out.update(cell.powerline())
    out[0x2580] = [cell.block(0, 4, 8, 8)]
    for i in range(1, 9):
        out[0x2580 + i] = [cell.block(0, 0, 8, i, "top" if i < 8 else ())]      # lower eighths: the bars of a sparkline
    for i in range(1, 8):
        out[0x2588 + i] = [cell.block(0, 0, 8 - i, 8, "right")]                 # left eighths: the end of a progress bar
    out[0x2590] = [cell.block(4, 0, 8, 8)]
    for i in (1, 2, 3):
        out[0x2590 + i] = cell.shade(i)
    out[0x2594] = [cell.block(0, 7, 8, 8)]
    out[0x2595] = [cell.block(7, 0, 8, 8)]
    for cp, parts in QUADRANTS.items():
        out[cp] = [cell.block(*QUARTER[p]) for p in parts]
    for bits in range(256):
        out[0x2800 + bits] = cell.braille(bits)
    return out
