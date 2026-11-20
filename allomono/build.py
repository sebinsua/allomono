"""Build allomono: `python -m allomono.build` writes the four fonts to fonts/.

Allo's glyphs (allo.py) are fitted to the cell (fit.py), slanted for the
italics, and assembled here into fonts with their features and names.
"""
import math
import os
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from . import outline as O
from .allo import PIXEL, ROOT, Allo, preferred
from .boxes import Cell, drawn
from .fit import CAP_SCALE, DASHES, Fitter, is_symbol

# The same sources always give the same files: the fonts carry this date, not the moment they were built.
os.environ.setdefault("SOURCE_DATE_EPOCH", "1795132800")   # 2026-11-20

FAMILY = "allomono"
VERSION = "0.1"
COPYRIGHT = (
    "Copyright 2026 Seb Insua. "
    "Based on Allo, Copyright 2026 Josh Puckett (https://joshpuckett.me), "
    "and Inter, Copyright (c) 2016 The Inter Project Authors (https://github.com/rsms/inter)."
)
LICENCE = "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: https://openfontlicense.org"

CELL = 1260   # 16 px at 13pt on a Retina display, so a terminal has nothing to round
OPEN = 3.5    # a letter with this many pixels clear on one side is open there: its neighbour leans in
LEAN = 2      # by at most this many pixels
SLANT = 9     # degrees, as Allo's obliques
# The weight of Allo each style is drawn from: sturdier than Allo's own Regular and Bold,
# because the bounce is in the fat strokes and a grid thins a face out.
# At 537 the stems are 3 px wide at 13pt on a Retina display.
STYLES = {"Regular": 537, "Bold": 800, "Italic": 537, "BoldItalic": 800}
STYLE_NAMES = {"Regular": "Regular", "Bold": "Bold", "Italic": "Italic", "BoldItalic": "Bold Italic"}
WIN_ASCENT, WIN_DESCENT = 2250, 600   # clipping bounds only: beyond the tallest accent in any style

# Typed arrows become Allo's arrows, drawn across both cells. Each keeps its two cells.
ARROWS = {"hyphen greater": "rightArrow", "equal greater": "rightDoubleArrow", "less hyphen": "leftArrow"}
# Alternates kept from Allo, under Allo's own feature tags.
ALTERNATES = {
    "ss01": ("Single-story a", lambda n: n + ".1" if n.startswith("a") else None),
    "ss03": ("Open figures", lambda n: n + ".ss01" if n in ("four", "six", "nine") else None),
    "cv05": ("Dotted zero", lambda n: "zero.dot" if n == "zero.slash" else None),
}


class Glyphs:
    """The font's glyphs as they are made: outlines, widths, and their order."""

    def __init__(self, order, lean, pivot):
        self.order, self.lean, self.pivot = list(order), lean, pivot
        self.outlines, self.advances, self.shapes, self.upright = {}, {}, {}, {}

    def add(self, name, shape, advance, upright=False):
        if name not in self.order:
            self.order.append(name)
        self.shapes[name], self.upright[name] = shape, upright
        if self.lean and not upright:
            shape = O.transform(shape, lambda p: (p[0] + (p[1] - self.pivot) * self.lean, p[1]))
        pen = TTGlyphPen(None)
        O.draw(O.union(shape) if shape else shape, pen)
        self.outlines[name] = pen.glyph()
        self.advances[name] = advance


def alternates(glyphs, fit, allo):
    """Allo's alternate forms, each behind its feature."""
    features = []
    for tag, (label, alternate) in ALTERNATES.items():
        pairs = [(n, alternate(n)) for n in list(glyphs.order) if alternate(n) in allo.names]
        for base, alt in pairs:
            if alt not in glyphs.outlines:
                fit.adopt(alt, base)                 # an alternate is fitted as the character it stands in for
                glyphs.add(alt, *fit.finished(alt)[:2])
        if pairs:
            subs = "\n".join(f"  sub {a} by {b};" for a, b in pairs)
            names = f'  featureNames {{ name "{label}"; }};\n' if tag.startswith("ss") else ""
            features.append(f"feature {tag} {{\n{names}{subs}\n}} {tag};")
    return features


def arrows(glyphs, fit, cell):
    """`->` and its kin: the first sign becomes an empty cell and the second the whole arrow, reaching back over it."""
    lookups = []
    for typed, arrow in ARROWS.items():
        first, last = typed.split()
        spacer, drawn = f"{first}_{last}.spacer", f"{first}_{last}.liga"
        glyphs.add(spacer, [], cell)
        glyphs.add(drawn, fit.arrow(arrow), cell, upright=True)
        # Allo's rule: only with a space or nothing either side, so p->next and --> stay as typed
        lookups.append(f"""  lookup {first}_{last} {{
    ignore sub @not_space {first}' {last};
    ignore sub {first}' {last} @not_space;
    sub {spacer} {last}' by {drawn};
    sub {first}' {last} by {spacer};
  }} {first}_{last};""")
    return lookups


def bars(glyphs, box, cmap, cell):
    """The bars of a sparkline. A bar's top corner is rounded only where it stands clear: beside a bar as
    tall or taller it is square, so a run of bars has no dips between them."""
    name = {i: cmap[0x2580 + i] for i in range(1, 9)}                 # eighths; 8 is the full block
    for i in range(1, 8):
        for suffix, soft in ((".r", "top left"), (".l", "top right"), (".lr", "")):   # the named sides are square
            glyphs.add(name[i] + suffix, [box.block(0, 0, 8, i, soft)], cell, upright=True)
    right, left = [], []
    for i in range(1, 8):
        tall = [name[k] for k in range(i, 9)]
        tall_any = tall + [name[k] + s for k in range(i, 8) for s in (".r", ".l", ".lr")]
        right.append(f"    sub {name[i]}' [{' '.join(tall)}] by {name[i]}.r;")
        left.append(f"    sub [{' '.join(tall_any)}] {name[i]}' by {name[i]}.l;")
        left.append(f"    sub [{' '.join(tall_any)}] {name[i]}.r' by {name[i]}.lr;")
    return ["  lookup bars_right {\n" + "\n".join(right) + "\n  } bars_right;", "  lookup bars_left {\n" + "\n".join(left) + "\n  } bars_left;"]


def heal(glyphs, cmap, cell):
    """Share out the empty space beside thin letters. Every character keeps its cell, but a letter next to
    the open side of a thin one (an l, an i, the right of a t) is drawn a pixel or two toward it, and the
    letter beyond follows by half as much. Two thin letters lean toward each other. Nothing is added to a
    letter and nothing is stretched: only where it stands in its cell changes with its neighbours."""
    names = [cmap[ord(c)] for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"]
    room = {n: (O.bounds(glyphs.shapes[n])[0], cell - O.bounds(glyphs.shapes[n])[2]) for n in names}
    open_left = [n for n in names if room[n][0] >= OPEN * PIXEL]
    open_right = [n for n in names if room[n][1] >= OPEN * PIXEL]

    def leaning(suffix, side, most):
        """Each letter moved toward one side by whole pixels, as far as `most` and the room it has allow."""
        out = []
        for n in names:
            pixels = min(most, int((room[n][side] + PIXEL / 2) // PIXEL))
            if pixels <= 0:
                out.append(n)
                continue
            glyphs.add(n + suffix, O.shift(glyphs.shapes[n], pixels * PIXEL * (1 if side else -1)), cell, upright=glyphs.upright[n])
            out.append(n + suffix)
        return out

    east, west = leaning(".east", 1, LEAN), leaning(".west", 0, LEAN)
    east_half, west_half = leaning(".east1", 1, LEAN // 2), leaning(".west1", 0, LEAN // 2)
    moved = lambda variants: [v for n, v in zip(names, variants) if v != n]  # noqa: E731
    group = lambda xs: "[" + " ".join(xs) + "]"  # noqa: E731
    after_open = group(open_right + [n + s for n in open_right for s in (".east", ".west") if n + s in glyphs.shapes])
    return [f"""  lookup lean {{
    ignore sub {after_open} {group(names)}' {group(open_left)};
    sub {group(names)}' {group(open_left)} by {group(east)};
    sub {after_open} {group(names)}' by {group(west)};
  }} lean;
  lookup follow {{
    sub {group(names)}' {group(moved(east))} by {group(east_half)};
    sub {group(moved(west))} {group(names)}' by {group(west_half)};
  }} follow;"""]


def assemble(style, glyphs, cmap, features, allo, cell, x_height, cap_height):
    """The font file: tables, names and metrics around the glyphs."""
    italic, bold = "Italic" in style, "Bold" in style
    source = allo.font
    fb = FontBuilder(source["head"].unitsPerEm, isTTF=True)
    fb.setupGlyphOrder(glyphs.order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs.outlines)
    glyf = fb.font["glyf"]
    hmtx = {}
    for name in glyphs.order:
        g = glyf[name]
        g.recalcBounds(glyf)
        hmtx[name] = (glyphs.advances[name], getattr(g, "xMin", 0) or 0)
    fb.setupHorizontalMetrics(hmtx)
    # The line is Allo's.
    hhea, os2 = source["hhea"], source["OS/2"]
    run = round(1000 * math.tan(math.radians(SLANT))) if italic else 0
    fb.setupHorizontalHeader(ascent=hhea.ascent, descent=hhea.descent, lineGap=0, caretSlopeRise=1000 if italic else 1, caretSlopeRun=run)
    fb.setupNameTable({
        "familyName": FAMILY,
        "styleName": STYLE_NAMES[style],
        "uniqueFontIdentifier": f"{FAMILY}-{style}-{VERSION}",
        "fullName": f"{FAMILY} {STYLE_NAMES[style]}",
        "psName": f"{FAMILY}-{style}",
        "version": f"Version {VERSION}",
        "copyright": COPYRIGHT,
        "licenseDescription": LICENCE,
        "licenseInfoURL": "https://openfontlicense.org",
    }, mac=False)  # fmt: skip
    top = max(getattr(glyf[n], "yMax", 0) or 0 for n in glyphs.order)
    bottom = min(getattr(glyf[n], "yMin", 0) or 0 for n in glyphs.order)
    assert top <= WIN_ASCENT and -bottom <= WIN_DESCENT, (top, bottom)
    fb.setupOS2(
        version=4, fsType=0,     # installable embedding: the OFL allows it
        sTypoAscender=os2.sTypoAscender, sTypoDescender=os2.sTypoDescender, sTypoLineGap=0,
        usWinAscent=WIN_ASCENT, usWinDescent=WIN_DESCENT,
        sxHeight=round(x_height), sCapHeight=round(cap_height),
        usWeightClass=700 if bold else 400, xAvgCharWidth=cell,
        fsSelection=0x80 | (0x20 if bold else 0) | (0x01 if italic else 0) | (0 if bold or italic else 0x40),
        achVendID="ALMO",
    )  # fmt: skip
    fb.font["OS/2"].panose.bFamilyType, fb.font["OS/2"].panose.bProportion = 2, 9     # Latin text, monospaced
    fb.font["head"].macStyle = (1 if bold else 0) | (2 if italic else 0)
    fb.font["head"].fontRevision = float(VERSION)
    # A 2 px underline two pixels clear of the baseline, and a strikethrough through the middle of the x-height.
    fb.setupPost(isFixedPitch=1, italicAngle=-SLANT if italic else 0, underlinePosition=-round(2 * PIXEL), underlineThickness=round(2 * PIXEL))
    fb.font["OS/2"].yStrikeoutSize = round(2 * PIXEL)
    fb.font["OS/2"].yStrikeoutPosition = round(x_height / 2 + PIXEL)
    addOpenTypeFeaturesFromString(fb.font, "\n".join(features))
    fb.font["OS/2"].recalcCodePageRanges(fb.font)
    weight = dict(value=700, name="Bold") if bold else dict(value=400, name="Regular", flags=0x2, linkedValue=700)
    posture = dict(value=1, name="Italic") if italic else dict(value=0, name="Roman", flags=0x2, linkedValue=1)
    buildStatTable(fb.font, [dict(tag="wght", name="Weight", values=[weight]), dict(tag="ital", name="Italic", values=[posture])], elidedFallbackName=2)
    fb.font["name"].names = [n for n in fb.font["name"].names if n.platformID == 3]
    return fb


def hint(path):
    """Autohint the font in place (ttfautohint), so that stems and heights snap to whole pixels where a
    rasteriser uses hints: Windows, and FreeType on Linux. macOS ignores them. Box drawing, blocks and
    symbols belong to no script and are left exactly as drawn, so they still join."""
    from ttfautohint import ttfautohint

    ttfautohint(in_file=str(path), out_file=str(path), no_info=True, epoch=int(os.environ["SOURCE_DATE_EPOCH"]), default_script="latn", fallback_script="none", hinting_range_min=8, hinting_range_max=60)
    font = TTFont(path)
    font["head"].flags |= 1 << 3          # a hinted font is set at whole pixel sizes
    font.save(path)


def build(style, wght, out, cell=None, rond=None):
    """Build one style. Returns how much each glyph was scaled to fit."""
    cell = cell or CELL
    allo = Allo(rond=rond)
    source = allo.font
    # Allo reaches its alternates through private-use codes. A terminal font must leave those alone: prompts
    # use the same codes for Powerline symbols, and Allo's raised division sign would answer for a branch mark.
    cmap = {cp: preferred(name, allo.names) for cp, name in source.getBestCmap().items() if not 0xE000 <= cp <= 0xF8FF}
    order = [".notdef"] + sorted(set(cmap.values()) - {".notdef"}, key=source.getGlyphID)
    chars = {}                                   # glyph name -> the first character it stands for
    for cp, name in sorted(cmap.items()):
        chars.setdefault(name, chr(cp))
    fit = Fitter(allo, wght, cell, chars)

    # Allo's obliques are its uprights slanted 9 degrees about half the x-height, with corrections
    # too small to see at text sizes; allomono's are its own uprights slanted the same way.
    lean = math.tan(math.radians(SLANT)) if "Italic" in style else 0
    x_height = allo.x_height(wght)
    # It leans about the middle of the tall letters rather than of the x-height, as Allo's does: in a cell,
    # that shares what leans out equally between the two sides.
    glyphs = Glyphs(order, lean, 19 * PIXEL / 2)
    scales = {}
    for name in order:
        shape, advance, scales[name], _ = fit.finished(name)
        # symbols stand upright in the italics, and so do the strokes that must meet their neighbours
        glyphs.add(name, shape, advance, upright=is_symbol(chars.get(name, "")) or chars.get(name, "") in DASHES)
    # Box drawing, blocks and braille are not in Allo: they are drawn, in its manner.
    box = Cell(cell, fit.bar)
    for cp, shape in drawn(box).items():
        if cp not in cmap:
            cmap[cp] = f"uni{cp:04X}"
            glyphs.add(cmap[cp], shape, cell, upright=True)
    # The arrows are in calt, which people turn off to keep operators as typed. The bars are in rclt, which
    # stays on, so a sparkline does not lose its joins with them.
    typed, joined = arrows(glyphs, fit, cell) + heal(glyphs, cmap, cell), bars(glyphs, box, cmap, cell)
    spaces = {cmap[cp] for cp in (0x20, 0xA0) if cp in cmap}
    not_space = "@not_space = [" + " ".join(n for n in glyphs.order if n not in spaces) + "];"
    features = alternates(glyphs, fit, allo) + [not_space, "feature calt {\n" + "\n".join(typed) + "\n} calt;", "feature rclt {\n" + "\n".join(joined) + "\n} rclt;"]

    out.parent.mkdir(exist_ok=True)
    assemble(style, glyphs, cmap, features, allo, cell, x_height, fit.cap * CAP_SCALE).save(out)
    hint(out)
    return scales


if __name__ == "__main__":
    for style, wght in STYLES.items():
        if sys.argv[1:] and style not in sys.argv[1:]:
            continue
        out = ROOT / "fonts" / f"{FAMILY}-{style}.ttf"
        scales = build(style, wght, out)
        hardest = sorted((s, n) for n, s in scales.items() if s < 0.8)[:5]
        print(f"{out.relative_to(ROOT)}  {len(scales)} glyphs; most condensed: " + ", ".join(f"{n} {s:.2f}" for s, n in hardest))
