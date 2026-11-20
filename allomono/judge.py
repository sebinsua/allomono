"""How well does it work as a monospace font? `python -m allomono.judge`

(How close it is to Allo is the other judge: allomono.likeness.)

It does not ask whether the letters look good. It asks what taste cannot
answer, at the size the font is used:

  - which characters could be mistaken for each other;
  - whether any ink leaves its cell, where a terminal may clip it;
  - how even the texture is: which glyphs are darker, lighter, thicker or thinner beside their neighbours
    than the same glyph is in an ordinary code font;
  - how exactly the cell lands on whole pixels at common sizes.

Every character is rasterised from the built font into its own cell, as at
13pt on a Retina display. Two characters are compared by how much of their ink
overlaps: 1.0 means the same picture, 0 means nothing in common. The same pair
is measured in an ordinary, well-regarded code font, and a pair is a problem
only when it is both alike and clearly more alike than it is there.
"""
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PPEM = 26  # 13pt on a Retina display
SUPER = 8  # supersampling: draw at 8x, average down to real pixels
THRESHOLD = 0.72
MARGIN = 0.08  # how much more alike than the reference font a pair may be
# Pairs where a misreading changes what code means are held to a much lower bar.
CRITICAL = [".,", ":;", ".:", ",;", "'`"]
CRITICAL_THRESHOLD = 0.45

# Pairs that are genuinely mistaken for each other in code and prose.
WATCH = [
    "nu", "nh", "hb", "ce", "co", "eo", "ao", "il", "l1", "lI", "I1", "i1", "O0", "o0", "OQ", "OD", "vy", "uv", "vw",
    "ft", "rn", "gq", "pq", "bd", "B8", "S5", "Z2", "G6", "g9", "q9", "z2", "sS", "cC", "xX", "vV", "wW", "zZ", "oO",
    ".,", ":;", "'`", "-_", "|l", "|I", "|1", "!i", "!l", "({", "[(", ")}", "])", "/|", "ij", "ae", "EF", "PR", "CG", "UV", "MN", "KX",
]  # fmt: skip

REFERENCES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "C:/Windows/Fonts/consola.ttf",
]
REFERENCE = next((f for f in REFERENCES if os.path.exists(f)), None)


class Face:
    def __init__(self, path, index=0):
        self.font = ImageFont.truetype(str(path), PPEM * SUPER, index=index)
        self.width = round(self.font.getlength("0"))
        self.ascent, self.descent = self.font.getmetrics()
        self.cache = {}

    def bitmap(self, ch):
        """The character in its cell, as grey levels 0..1."""
        if ch not in self.cache:
            img = Image.new("L", (self.width, self.ascent + self.descent), 0)
            ImageDraw.Draw(img).text((0, 0), ch, font=self.font, fill=255)
            small = img.resize((max(1, self.width // SUPER), max(1, (self.ascent + self.descent) // SUPER)), Image.BOX)
            self.cache[ch] = [v / 255 for v in small.tobytes()]
        return self.cache[ch]

    def alike(self, a, b):
        """Shared ink over total ink."""
        x, y = self.bitmap(a), self.bitmap(b)
        total = sum(max(p, q) for p, q in zip(x, y))
        return sum(min(p, q) for p, q in zip(x, y)) / total if total else 1.0


def reference_for(path):
    """The reference font in the matching weight (Menlo keeps its bold second in the file)."""
    if not REFERENCE:
        return None
    try:
        return Face(REFERENCE, 1 if "Bold" in Path(path).stem and REFERENCE.endswith(".ttc") else 0)
    except OSError:
        return Face(REFERENCE)


def texture(face):
    """How uneven the lowercase is: the spread of ink per letter over its mean. Lower is more even."""
    ink = [sum(face.bitmap(ch)) for ch in "abcdefghijklmnopqrstuvwxyz"]
    mean = sum(ink) / len(ink)
    return (sum((v - mean) ** 2 for v in ink) / len(ink)) ** 0.5 / mean


def overflow(path):
    """Glyphs whose ink leaves the cell sideways, which a terminal may clip."""
    from fontTools.ttLib import TTFont

    font = TTFont(path)
    glyf, hmtx = font["glyf"], font["hmtx"]
    out = []
    for name in font.getGlyphOrder():
        g, adv = glyf[name], hmtx[name][0]
        joins = name.endswith(".liga") or (name.startswith("uni") and (0x23BF <= int(name[3:7], 16) < 0x25A0 or 0xE0B0 <= int(name[3:7], 16) <= 0xE0B7))   # meant to reach the next cell
        if g.numberOfContours and adv and not joins and (g.xMin < -1 or g.xMax > adv + 1):
            out.append((max(-g.xMin, g.xMax - adv), name))
    return sorted(out, reverse=True), {hmtx[n][0] for n in font.getGlyphOrder()} - {0}, font["head"].unitsPerEm


GROUPS = [   # name, its characters, the letter whose height is the band measured, the letter whose stroke is the standard
    ("lowercase", "abcdefghijklmnopqrstuvwxyz", "x", "n"),
    ("capitals", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "H", "H"),
    ("figures and signs", "0123456789%&@#$", "H", "H"),
]
DENSITY = (0.82, 1.25)   # how much darker or lighter than in the reference font a glyph may be, each beside its own group
STROKE = (0.75, 1.35)    # and how much thicker or thinner its strokes
# Differences that are choices, not faults: i has no flag or foot here, and the zero's slash is Allo's, a thin one.
BARE = "i0"


def _mask(face, ch):
    """The character at full drawing size, before it is averaged down to pixels."""
    img = Image.new("L", (face.width, face.ascent + face.descent), 0)
    ImageDraw.Draw(img).text((0, 0), ch, font=face.font, fill=255)
    return img


def _measure(face, chars, band_of, standard):
    """For each character: how dense its ink is within the band (the x-height for lowercase, the cap height
    for the rest, so that ascenders and descenders do not count), beside its group's mean; and how thick
    its strokes are where a level line crosses them, beside the standard letter's."""
    box = _mask(face, band_of).getbbox()
    top, bottom = box[1], box[3]
    rows = [top + round((bottom - top) * f) for f in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)]

    def stroke(img):
        runs = []
        for y in rows:
            line = img.crop((0, y, img.width, y + 1)).tobytes()
            run = 0
            for v in line + b"\x00":
                if v > 127:
                    run += 1
                elif run:
                    runs.append(run)
                    run = 0
        runs.sort()                       # the thinner crossings are the strokes; the long ones are bars and bowls met side on
        return runs[len(runs) // 4] if runs else 0

    masks = {ch: _mask(face, ch) for ch in chars + standard}
    ink = {ch: sum(masks[ch].crop((0, top, face.width, bottom)).tobytes()) for ch in chars}
    mean = sum(ink.values()) / len(ink)
    unit = stroke(masks[standard]) or 1
    return {ch: (ink[ch] / mean, stroke(masks[ch]) / unit) for ch in chars}


def uneven(face, ref):
    """Glyphs that are darker, lighter, thicker or thinner beside their group than the same glyph is in the
    reference font. An i is light in any monospace and an m dark; this asks only whether ours is more so."""
    out = []
    for _, chars, band_of, standard in GROUPS:
        ours, theirs = _measure(face, chars, band_of, standard), _measure(ref, chars, band_of, standard)
        for ch in chars:
            density, stroke = ours[ch][0] / theirs[ch][0], (ours[ch][1] / theirs[ch][1] if theirs[ch][1] else 1)
            if ch not in BARE and (not DENSITY[0] <= density <= DENSITY[1] or not STROKE[0] <= stroke <= STROKE[1]):
                out.append((ch, density, stroke))
    return out


def judge(path):
    face = Face(path)
    ref = reference_for(path)
    chars = [chr(c) for c in range(33, 127)]
    pairs = {frozenset(p): (p[0], p[1]) for p in WATCH}
    for i, a in enumerate(chars):
        for b in chars[i + 1 :]:
            if frozenset((a, b)) not in pairs and face.alike(a, b) >= THRESHOLD:
                pairs[frozenset((a, b))] = (a, b)
    rows, problems = [], []
    for a, b in pairs.values():
        s = face.alike(a, b)
        r = ref.alike(a, b) if ref else 0.0
        critical = a + b in CRITICAL or b + a in CRITICAL
        bad = s >= (CRITICAL_THRESHOLD if critical else THRESHOLD) and s - r > MARGIN
        rows.append((s, r, a, b, critical, bad))
        if bad:
            problems.append((a, b))
    rows.sort(reverse=True)
    name = Path(REFERENCE).stem if REFERENCE else "no reference font"
    print("%s: how alike two characters are at 13pt (1.00 = identical), with the same pair in %s in brackets." % (Path(path).stem, name))
    line = ["%s %s %.2f (%.2f)%s%s" % (a, b, s, r, "*" if c else " ", "!" if bad else " ") for s, r, a, b, c, bad in rows[:30]]
    for i in range(0, len(line), 5):
        print("   " + "   ".join(line[i : i + 5]))
    print("   %d pair(s) both alike and clearly more alike than in %s%s" % (len(problems), name, ": " + ", ".join("%s/%s" % p for p in problems) if problems else "."))
    spilled, advances, upm = overflow(path)
    print("   advances: %s" % ("one width, %d units" % advances.pop() if len(advances) == 1 else "NOT monospaced: %s" % sorted(advances)))
    print("   ink outside the cell: %s" % (", ".join("%s %d" % (n, d) for d, n in spilled[:8]) if spilled else "none"))
    print("   texture (unevenness of the lowercase): %.3f%s" % (texture(face), ", %s %.3f" % (name, texture(ref)) if ref else ""))
    rough = uneven(face, ref) if ref else []
    print("   uneven beside %s (density, stroke; 1.00 = as there): %s" % (name, "  ".join("%s %.2f %.2f" % r for r in rough) if rough else "none"))
    adv = face.font.getlength("0") / SUPER / PPEM
    print("   cell in pixels on a Retina display: " + "  ".join("%gpt %.2f" % (pt, adv * pt * 2) for pt in (11, 12, 13, 14, 15, 16)) + "\n")
    problems = problems + [r[0] for r in rough]
    return problems if "Italic" in Path(path).stem else problems + [n for d, n in spilled if d > 8]    # an upright must stay in its cell


if __name__ == "__main__":
    fonts = sys.argv[1:] or [ROOT / "fonts" / f"allomono-{s}.ttf" for s in ("Regular", "Bold", "Italic", "BoldItalic")]
    sys.exit(1 if any([judge(f) for f in fonts]) else 0)
