"""Outlines as plain data, and the few operations the mono letters need.

A shape is a list of closed contours; a contour is a list of segments, each
("L", p0, p1) or ("Q", p0, control, p1).
"""
import math

from fontTools.pens.basePen import decomposeQuadraticSegment
from fontTools.pens.recordingPen import RecordingPen
from pathops import Path

KAPPA = 0.5523


def from_recording(value):
    shape, contour, start, cur = [], [], None, None
    for op, args in value:
        if op == "moveTo":
            start = cur = args[0]
            contour = []
        elif op == "lineTo":
            contour.append(("L", cur, args[0]))
            cur = args[0]
        elif op == "qCurveTo":
            if args[-1] is None:          # a contour with no on-curve points
                offs = list(args[:-1])
                mids = [_mid(offs[i - 1], offs[i]) for i in range(len(offs))]
                contour = [("Q", mids[i], offs[i], mids[(i + 1) % len(offs)]) for i in range(len(offs))]
                shape.append(contour)
                contour, start, cur = [], None, None
                continue
            for c, p in decomposeQuadraticSegment(args):
                contour.append(("Q", cur, c, p))
                cur = p
        elif op in ("closePath", "endPath"):
            if contour:
                if _far(cur, start):
                    contour.append(("L", cur, start))
                shape.append(contour)
            contour = []
        else:
            raise ValueError(op)
    return shape


def draw(shape, pen):
    for contour in shape:
        if not contour:
            continue
        pen.moveTo(contour[0][1])
        for seg in contour:
            if seg[0] == "L":
                pen.lineTo(seg[2])
            else:
                pen.qCurveTo(seg[2], seg[3])
        pen.closePath()


def _mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _far(a, b):
    return abs(a[0] - b[0]) > 1e-6 or abs(a[1] - b[1]) > 1e-6


def points(shape):
    for contour in shape:
        for seg in contour:
            yield from seg[1:]


def bounds(shape):
    """The outline's exact extent: its on-curve points, and each curve where it turns back."""
    xs, ys = [], []
    for contour in shape:
        for seg in contour:
            ts = [0, 1]
            if seg[0] == "Q":
                for k in (0, 1):
                    a = seg[1][k] - 2 * seg[2][k] + seg[3][k]
                    if abs(a) > 1e-9 and 0 < (seg[1][k] - seg[2][k]) / a < 1:
                        ts.append((seg[1][k] - seg[2][k]) / a)
            for t in ts:
                x, y = at(seg, t)
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def at(seg, t):
    if seg[0] == "L":
        (x0, y0), (x1, y1) = seg[1], seg[2]
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
    (x0, y0), (xc, yc), (x1, y1) = seg[1:]
    u = 1 - t
    return u * u * x0 + 2 * u * t * xc + t * t * x1, u * u * y0 + 2 * u * t * yc + t * t * y1


def transform(shape, fn):
    return [[(seg[0],) + tuple(fn(p) for p in seg[1:]) for seg in contour] for contour in shape]


def shift(shape, dx, dy=0):
    return transform(shape, lambda p: (p[0] + dx, p[1] + dy))


def scale_x(shape, s, about=0):
    return transform(shape, lambda p: (about + (p[0] - about) * s, p[1]))


def _split(seg, ts):
    """Cut a segment at the parameters ts (ascending, inside 0..1)."""
    out, prev = [], 0.0
    for t in ts:
        local = (t - prev) / (1 - prev)
        a, seg = _split1(seg, local)
        out.append(a)
        prev = t
    out.append(seg)
    return out


def _split1(seg, t):
    if seg[0] == "L":
        m = at(seg, t)
        return ("L", seg[1], m), ("L", m, seg[2])
    p0, c, p1 = seg[1:]
    a = (p0[0] + (c[0] - p0[0]) * t, p0[1] + (c[1] - p0[1]) * t)
    b = (c[0] + (p1[0] - c[0]) * t, c[1] + (p1[1] - c[1]) * t)
    m = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return ("Q", p0, a, m), ("Q", m, b, p1)


def _crossings(seg, cut):
    if seg[0] == "L":
        x0, x1 = seg[1][0], seg[2][0]
        if (x0 - cut) * (x1 - cut) < 0:
            return [(cut - x0) / (x1 - x0)]
        return []
    x0, xc, x1 = seg[1][0], seg[2][0], seg[3][0]
    a, b, c = x0 - 2 * xc + x1, 2 * (xc - x0), x0 - cut
    if abs(a) < 1e-9:
        roots = [-c / b] if abs(b) > 1e-9 else []
    else:
        disc = b * b - 4 * a * c
        if disc < 0:
            return []
        r = math.sqrt(disc)
        roots = [(-b - r) / (2 * a), (-b + r) / (2 * a)]
    return sorted(t for t in roots if 1e-6 < t < 1 - 1e-6)


def stretch(shape, cut, d):
    """Pull everything beyond x=cut away by d, bridging the gap with straight lines.

    d > 0 moves what lies right of the cut to the right; d < 0 moves what lies
    left of it to the left. Cut where the outline runs level and nothing bends.
    """
    moving_right = d > 0
    out = []
    for contour in shape:
        pieces = []
        for seg in contour:
            ts = _crossings(seg, cut)
            pieces.extend(_split(seg, ts) if ts else [seg])
        moved = []
        for seg in pieces:
            x = at(seg, 0.5)[0]
            if (x > cut) == moving_right:
                moved.append((seg[0],) + tuple((p[0] + d, p[1]) for p in seg[1:]))
            else:
                moved.append(seg)
        rebuilt = []
        for i, seg in enumerate(moved):
            prev = moved[i - 1]
            if _far(prev[-1], seg[1]):
                rebuilt.append(("L", prev[-1], seg[1]))
            rebuilt.append(seg)
        out.append(rebuilt)
    return out


def swell(shape, cut, d):
    """Pull everything beyond x=cut away by d, and let the curves that arrive at the cut grow to meet it.

    Like stretch, but nothing straight is inserted: each run of curve between the
    cut and the stem it springs from is widened about the stem. A level stroke
    simply gets longer.
    """
    moving_right = d > 0
    sign = 1 if moving_right else -1
    out = []
    for contour in shape:
        pieces = []
        for seg in contour:
            ts = _crossings(seg, cut)
            pieces.extend(_split(seg, ts) if ts else [seg])
        n = len(pieces)
        moves = [((at(seg, 0.5)[0] > cut) == moving_right) for seg in pieces]
        if not any(moves) or all(moves):
            out.append([_shift_seg(seg, d) if m else seg for seg, m in zip(pieces, moves)])
            continue
        factor = {}                                   # piece index -> (anchor x, factor)
        for i in range(n):
            for step in (1, -1):                      # the still side lies after (1) or before (-1) the moving piece
                j = (i + step) % n
                if not moves[i] or moves[j]:
                    continue
                chain, k = [], j
                while not moves[k] and k not in factor and len(chain) < n:
                    seg = pieces[k]
                    near, far = (seg[1], seg[-1]) if step == 1 else (seg[-1], seg[1])
                    if (near[0] - far[0]) * sign <= 0.5:      # upright, or turning back toward the cut
                        break
                    chain.append(k)
                    k = (k + step) % n
                if not chain:
                    continue
                last = pieces[chain[-1]]
                anchor = (last[-1] if step == 1 else last[1])[0]
                span = abs(cut - anchor)
                for k in chain:
                    factor[k] = (anchor, (span + abs(d)) / span)
        moved = []
        for k, seg in enumerate(pieces):
            if moves[k]:
                moved.append(_shift_seg(seg, d))
            elif k in factor:
                a, f = factor[k]
                moved.append((seg[0],) + tuple((a + (p[0] - a) * f, p[1]) for p in seg[1:]))
            else:
                moved.append(seg)
        rebuilt = []
        for i, seg in enumerate(moved):
            prev = moved[i - 1]
            if _far(prev[-1], seg[1]):
                rebuilt.append(("L", prev[-1], seg[1]))
            rebuilt.append(seg)
        out.append(rebuilt)
    return out


def _shift_seg(seg, d):
    return (seg[0],) + tuple((p[0] + d, p[1]) for p in seg[1:])


def lower_top(shape, above, dy):
    """Move everything above the height `above` by dy: shortens or lengthens an upright stem."""
    return transform(shape, lambda p: (p[0], p[1] + dy) if p[1] > above else p)


def excise(shape, a, b):
    """Remove the band of the outline between x=a and x=b and close the gap.

    Returns None unless the outline runs level through the whole band, which
    is what makes removing it harmless.
    """
    out = []
    for contour in shape:
        pieces = []
        for seg in contour:
            ts = sorted(set(_crossings(seg, a) + _crossings(seg, b)))
            pieces.extend(_split(seg, ts) if ts else [seg])
        kept = []
        for seg in pieces:
            x = at(seg, 0.5)[0]
            if a < x < b:
                if seg[0] != "L" or abs(seg[1][1] - seg[2][1]) > 0.5:
                    return None
                continue
            if x >= b:
                seg = (seg[0],) + tuple((p[0] - (b - a), p[1]) for p in seg[1:])
            kept.append(seg)
        rebuilt = []
        for i, seg in enumerate(kept):
            prev = kept[i - 1]
            if _far(prev[-1], seg[1]):
                if abs(prev[-1][1] - seg[1][1]) > 0.5 and abs(prev[-1][0] - seg[1][0]) > 0.5:
                    return None
                rebuilt.append(("L", prev[-1], seg[1]))
            rebuilt.append(seg)
        if rebuilt:
            out.append(rebuilt)
    return out


def scale(shape, s, about):
    ax, ay = about
    return transform(shape, lambda p: (ax + (p[0] - ax) * s, ay + (p[1] - ay) * s))


def level_x(shape, want, x_min=-1e9, x_max=1e9):
    """The x at which the outline is highest (want="top") or lowest ("bottom") between x_min and x_max."""
    best = None
    for contour in shape:
        for seg in contour:
            for i in range(33):
                x, y = at(seg, i / 32)
                if x_min <= x <= x_max:
                    key = y if want == "top" else -y
                    if best is None or key > best[0]:
                        best = (key, x)
    return best[1]


def rounded_rect(x0, y0, x1, y1, r):
    """A rectangle with rounded corners. `r` is one radius, or four: bottom left, bottom right, top right, top left."""
    radii = [r] * 4 if isinstance(r, (int, float)) else list(r)
    radii = [min(q, (x1 - x0) / 2, (y1 - y0) / 2) for q in radii]
    corners = [((x0, y0), (0, 1), (1, 0)), ((x1, y0), (-1, 0), (0, 1)), ((x1, y1), (0, -1), (-1, 0)), ((x0, y1), (1, 0), (0, -1))]
    ends = []     # for each corner (counter-clockwise): where its curve starts and ends, and the two controls
    for ((x, y), into, out), q in zip(corners, radii):
        k = q * (1 - KAPPA)
        ends.append(((x + into[0] * q, y + into[1] * q), (x + out[0] * q, y + out[1] * q), (x + into[0] * k, y + into[1] * k), (x + out[0] * k, y + out[1] * k)))
    contour = []
    for i, (before, after, c1, c2) in enumerate(ends):
        if _far(before, after):
            m = _mid(c1, c2)
            contour.append(("Q", before, c1, m))
            contour.append(("Q", m, c2, after))
        nxt = ends[(i + 1) % 4][0]
        if _far(after, nxt):
            contour.append(("L", after, nxt))
    return reverse(contour)       # clockwise, as Allo's outer contours are


def reverse(contour):
    return [(seg[0],) + tuple(reversed(seg[1:])) for seg in reversed(contour)]


def clockwise(contour):
    return reverse(contour) if area(contour) > 0 else contour


def subtract(shape, hole):
    """`shape` with everything inside `hole` removed."""
    from pathops import PathOp, op

    a, b = Path(), Path()
    draw(shape, a.getPen())
    draw(hole, b.getPen())
    rec = RecordingPen()
    op(a, b, PathOp.DIFFERENCE, fix_winding=True, keep_starting_points=False).draw(rec)
    return _outer_clockwise(from_recording(rec.value))


def _outer_clockwise(shape):
    """Every merged outline runs the same way, so that merging two of them again never cancels their overlap."""
    if shape and max((area(c) for c in shape), key=abs) > 0:
        return [reverse(c) for c in shape]
    return shape


def union(shape):
    """Merge overlapping contours into clean outlines."""
    path = Path()
    draw(shape, path.getPen())
    path.simplify(fix_winding=True, keep_starting_points=False)
    rec = RecordingPen()
    path.draw(rec)
    return _outer_clockwise(from_recording(rec.value))


def span_at(shape, y):
    """Leftmost and rightmost x where the outline crosses the height y."""
    xs = []
    for contour in shape:
        for seg in contour:
            prev = at(seg, 0)
            for i in range(1, 33):
                cur = at(seg, i / 32)
                if (prev[1] - y) * (cur[1] - y) <= 0 and prev[1] != cur[1]:
                    xs.append(prev[0] + (cur[0] - prev[0]) * (y - prev[1]) / (cur[1] - prev[1]))
                prev = cur
    return min(xs), max(xs)


def area(contour):
    """Signed area of a contour's corner points: its sign is the direction it runs."""
    pts = [seg[1] for seg in contour]
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2


def turning_like(shape, model):
    """`shape`, reversed if need be so its outer contour runs the same way as `model`'s."""
    if not shape or not model:
        return shape
    a = max((area(c) for c in shape), key=abs)
    b = max((area(c) for c in model), key=abs)
    return [reverse(c) for c in shape] if a * b < 0 else shape


def level_span(shape):
    """The widest stretch of x over which the outline is nothing but level lines: a shaft or a bar."""
    b = bounds(shape)
    steps = 240
    xs = [b[0] + (b[2] - b[0]) * (i + 0.5) / steps for i in range(steps)]
    ok = []
    for x in xs:
        level, crossed = True, False
        for contour in shape:
            for seg in contour:
                lo, hi = min(p[0] for p in seg[1:]), max(p[0] for p in seg[1:])
                if lo < x < hi:
                    crossed = True
                    if seg[0] != "L" or abs(seg[1][1] - seg[2][1]) > 0.5:
                        level = False
        ok.append(level and crossed)             # empty space between two parts is not a shaft
    best, start = None, None
    for i, flag in enumerate(ok + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if best is None or i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    if best is None:
        return None
    return xs[best[0]], xs[best[1] - 1]
