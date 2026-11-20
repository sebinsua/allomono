"""How close is allomono to Allo? `python -m allomono.likeness`

Unlike a font drawn from nothing, allomono has an original to be held against.
This sets the two side by side the way Allo presents itself (the greetings from
its own specimen, at its own roundness and display size), and then measures,
letter by letter, what the monospace fitting changed:

  shape  how alike the two letters are once each is stretched to the same box,
         so a change of width alone does not count against it (1.00 = identical)
  wide   allomono's width over Allo's
  ink    how dark the letter is in its box, allomono over Allo: stroke weight

Letters that were redrawn for the cell are listed apart: they are meant to differ.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .allo import OPSZ, ROND
from .build import STYLES

ROOT = Path(__file__).resolve().parent.parent
ALLO = ROOT / "upstream/allo/fonts/variable/AlloVariable.ttf"
WEIGHTS = {s: w for s, w in STYLES.items() if "Italic" not in s}   # the weight of Allo each style is drawn from
REDRAWN = "ijlftrI1"
GREETINGS = [
    ("Hello", "#ff0a3b", "Bold"), ("Hola", "#00c9a7", "Regular"), ("Ciao", "#0a84ff", "Regular"), ("Hallo", "#ff8a00", "Bold"),
    ("Salut", "#00b8e6", "Bold"), ("Moi", "#6b5cff", "Bold"), ("Tere", "#ffcc00", "Regular"), ("Salve", "#12c94a", "Regular"),
    ("Halo", "#e010e0", "Bold"), ("Servus", "#ff0a3b", "Bold"), ("Szia", "#0a84ff", "Bold"), ("Merhaba", "#ff8a00", "Bold"),
    ("Bok", "#b07c56", "Bold"), ("Bonjour", "#ff0055", "Bold"), ("Ahoj", "#00b8e6", "Regular"), ("Hej", "#6b5cff", "Regular"),
]  # fmt: skip


def allo(size, wght, rond=ROND, opsz=OPSZ):
    font = ImageFont.truetype(str(ALLO), size)
    axes = [a["name"] if isinstance(a["name"], str) else a["name"].decode() for a in font.get_variation_axes()]
    values = {"Optical size": opsz, "Weight": wght, "Roundness": rond}
    font.set_variation_by_axes([values.get(n, a["default"]) for n, a in zip(axes, font.get_variation_axes())])
    return font


FONTS = ROOT / "fonts"


def mono(size, style):
    return ImageFont.truetype(str(FONTS / f"allomono-{style}.ttf"), size)


def greetings(out, size=92):
    """Allo's own greetings, each in Allo (above) and allomono (below)."""
    cols, pad, row = 4, 40, int(size * 2.75)
    width = 2200
    img = Image.new("RGB", (width, pad * 2 + row * (len(GREETINGS) // cols)), "#fcfcfc")
    d = ImageDraw.Draw(img)
    for i, (word, colour, style) in enumerate(GREETINGS):
        x, y = pad + (i % cols) * (width - 2 * pad) // cols, pad + (i // cols) * row
        d.text((x, y), word, font=allo(size, WEIGHTS[style]), fill=colour)
        d.text((x, y + size * 1.2), word, font=mono(size, style), fill=colour)
    img.save(out)
    return out


def _box(font, ch, size=96):
    """The letter alone, stretched to a square box; and its ink width, height and darkness."""
    canvas = Image.new("L", (size * 6, size * 6), 0)
    ImageDraw.Draw(canvas).text((size * 2, size * 2), ch, font=font, fill=255)
    bbox = canvas.getbbox()
    if bbox is None:
        return None
    crop = canvas.crop(bbox)
    w, h = crop.size
    dark = sum(crop.tobytes()) / 255 / (w * h)
    return crop.resize((size, size), Image.BILINEAR), w, h, dark


def compare(style, chars, ppem=400):
    a_font, m_font = allo(ppem, WEIGHTS[style]), mono(ppem, style)
    rows = []
    for ch in chars:
        a, m = _box(a_font, ch), _box(m_font, ch)
        if not a or not m:
            continue
        x, y = a[0].tobytes(), m[0].tobytes()
        total = sum(max(p, q) for p, q in zip(x, y))
        rows.append((ch, sum(min(p, q) for p, q in zip(x, y)) / total, m[1] / a[1], m[2] / a[2], m[3] / a[3]))
    return rows


def report(style):
    groups = [("lowercase", "abcdefghijklmnopqrstuvwxyz"), ("capitals", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"), ("figures", "0123456789"), ("signs", "#$%&@(){}[]<>?!*+=/")]
    print(f"{style}: allomono against Allo at weight {WEIGHTS[style]}, roundness 50")
    for label, chars in groups:
        rows = compare(style, chars)
        kept = [r for r in rows if r[0] not in REDRAWN]
        mean = lambda i: sum(r[i] for r in kept) / len(kept)  # noqa: E731
        worst = sorted(kept, key=lambda r: r[1])[:5]
        print(f"   {label:9} shape {mean(1):.2f}   wide {mean(2):.2f}   tall {mean(3):.2f}   ink {mean(4):.2f}   least alike: " + "  ".join(f"{r[0]} {r[1]:.2f}" for r in worst))
    redrawn = compare(style, REDRAWN)
    print("   redrawn   " + "  ".join(f"{r[0]} shape {r[1]:.2f} wide {r[2]:.2f}" for r in redrawn))
    print()


# What "still Allo" means, in numbers. Each was set from a build that looked right, with room either side;
# a change that leaves these ranges has changed the look, and has to be looked at.
RANGES = {
    "lowercase shape": (0.88, 1.0),      # mean likeness of the letters that were not redrawn
    "capital shape": (0.85, 1.0),        # lower than the lowercase: W, M and V are condensed
    "lowercase ink": (0.92, 1.10),       # stroke weight beside Allo's, so it is neither thinned nor clogged
    "capital ink": (0.95, 1.15),
    "hole": (0.78, 1.06),                # width over height of each letter's counter, beside Allo's: 1 is the same shape.
                                         # The cell is narrow and the letters are narrowed to fit it, on purpose.
    "capital hole": (0.66, 1.06),        # capitals are allowed a little narrower: O and Q do not fit a cell whole
    "texture": (0.72, 1.05),             # how dark a line of text is beside Allo's: a monospace has more air, not less ink
}
HOLED = "abdegopq"
CAPITAL_HOLED = "BDOPQR"       # not A: its counter is a wedge between two diagonals, which no fitting keeps


def _hole(font, ch, location=None):
    """Width over height of the largest counter in a letter."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen

    from . import outline as O

    glyphs = font.getGlyphSet(location=location) if location else font.getGlyphSet()
    name = font.getBestCmap()[ord(ch)]
    rec = DecomposingRecordingPen(glyphs)
    glyphs[name].draw(rec)
    shape = O.union(O.from_recording(rec.value))
    outer = max(shape, key=lambda c: abs(O.area(c)))
    holes = [c for c in shape if O.area(c) * O.area(outer) < 0]
    if not holes:
        return None
    b = O.bounds([max(holes, key=lambda c: abs(O.area(c)))])
    return (b[2] - b[0]) / (b[3] - b[1])


def holes(style, chars):
    """For each letter, its counter's proportions over the same counter's in Allo."""
    from fontTools.ttLib import TTFont

    ours, theirs = TTFont(FONTS / f"allomono-{style}.ttf"), TTFont(ALLO)
    location = {"wght": WEIGHTS[style], "opsz": OPSZ, "ROND": ROND}
    return {ch: _hole(ours, ch) / _hole(theirs, ch, location) for ch in chars}


def texture(style, size=200):
    """Ink in the x-height band of a line of text, allomono's over Allo's."""
    text = "the quick brown fox jumps over a lazy dog"
    out = []
    for font in (mono(size, style), allo(size, WEIGHTS[style])):
        img = Image.new("L", (int(font.getlength(text)) + 40, size * 2), 0)
        ImageDraw.Draw(img).text((20, size // 2), text, font=font, fill=255)
        x_box = font.getbbox("x")
        band = img.crop((20, size // 2 + x_box[1], img.width - 20, size // 2 + x_box[3]))
        out.append(sum(band.tobytes()) / 255 / (band.width * band.height))
    return out[0] / out[1]


def verdict(style):
    """Hold the style against RANGES. Returns the names of what fell outside."""
    lower = [r for r in compare(style, "abcdefghijklmnopqrstuvwxyz") if r[0] not in REDRAWN + "m"]
    upper = compare(style, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    mean = lambda rows, i: sum(r[i] for r in rows) / len(rows)  # noqa: E731
    measured = [
        ("lowercase shape", "lowercase shape", mean(lower, 1)),
        ("capital shape", "capital shape", mean(upper, 1)),
        ("lowercase ink", "lowercase ink", mean(lower, 4)),
        ("capital ink", "capital ink", mean(upper, 4)),
        ("texture", "texture", texture(style)),
    ]
    measured += [(f"hole in {ch}", "hole", v) for ch, v in holes(style, HOLED).items()]
    measured += [(f"hole in {ch}", "capital hole", v) for ch, v in holes(style, CAPITAL_HOLED).items()]
    failed = []
    for label, kind, value in measured:
        lo, hi = RANGES[kind]
        ok = lo <= value <= hi
        if not ok:
            failed.append(label)
        if not ok or kind not in ("hole", "capital hole"):
            print(f"   {'pass' if ok else 'FAIL'}  {label:16} {value:.2f}   ({lo:.2f} to {hi:.2f})")
    counters = [v for _, kind, v in measured if kind in ("hole", "capital hole")]
    print(f"   {'pass' if not any('hole' in f for f in failed) else 'FAIL'}  holes            {min(counters):.2f} to {max(counters):.2f} across {HOLED + CAPITAL_HOLED}")
    return failed


if __name__ == "__main__":
    print(greetings(ROOT / "proofs" / "likeness-greetings.png"), "\n")
    failed = []
    for style in WEIGHTS:
        report(style)
        failed += verdict(style)
        print()
    print("Still Allo by every measure." if not failed else "Outside its ranges: " + ", ".join(failed))
    sys.exit(1 if failed else 0)
