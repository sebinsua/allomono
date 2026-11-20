"""Draw the README's pictures: `python -m allomono.specimen` writes docs/hello.png and docs/characters.png.

Everything on them is set by the same renderer used to check the font (eyes.py),
so they show what a terminal shows, not an idealised drawing.
"""
import hashlib
import re
import tempfile
from pathlib import Path

from PIL import Image

from .eyes import BG, ROOT, render

B, I, DIM, R = "\x1b[1m", "\x1b[3m", "\x1b[2m", "\x1b[0m"
KEY, STR, NUM, FN = "\x1b[38;5;110m", "\x1b[38;5;180m", "\x1b[38;5;174m", "\x1b[38;5;252m"

CODE = (
    f"{DIM}{I}// count how often each word appears{R}\n"
    f"{KEY}fn{R} {FN}word_counts{R}(text: &{KEY}str{R}) -> HashMap<&{KEY}str{R}, {KEY}usize{R}> {{\n"
    f"    {KEY}let mut{R} counts = HashMap::new();\n"
    f"    {KEY}for{R} word {KEY}in{R} text.split_whitespace() {{\n"
    f"        *counts.entry(word).or_insert({NUM}0{R}) += {NUM}1{R};\n"
    f"    }}\n"
    f"    counts\n"
    f"}}"
)

BLOCKS = [
    (96, "allomono"),
    (22, DIM + "a friendly monospace font, made from Allo" + R),
    (30, "abcdefghijklm nopqrstuvwxyz\nABCDEFGHIJKLM NOPQRSTUVWXYZ\n0123456789  (){}[]<>  !?&@#$%"),
    (17, CODE),
    (24, "a -> b   x => y   a <- b   == != <= >= :: ++"),
    (24, f"Regular  {B}Bold{R}  {I}Italic{R}  {B}{I}Bold Italic{R}"),
    (20, "àéîõü ÀÉÎÕÜ  çñßøåł  café naïve señor fjörd"),
    (20, "← → ↑ ↓ ⇒  ⌘ ⌥ ⇧ ⏎ ⌫  ✓ ✗ ★ ♥ ⚠  ▁▂▃▅▇  ⠋⠙⠹"),
]

# The picture at the top of the README: Allo's own greetings, in its colours, over a few lines of code.
PAPER, INK = "#fcfcfc", "#111111"
RED, TEAL, BLUE, ORANGE, CYAN, VIOLET = "#ff0a3b", "#00c2a0", "#0a84ff", "#ff8a00", "#00b4e0", "#6b5cff"
YELLOW, GREEN, PINK, BROWN, MAGENTA, GREY = "#f5b800", "#12b84a", "#ff0f7b", "#b07c56", "#dc14dc", "#8a8f98"

GREETINGS = [   # each row is 27 cells: words and the symbols between them, as (text, colour, style)
    [("Hello", RED, B), ("★", RED, ""), ("Hola", TEAL, ""), ("⌫", TEAL, ""), ("Ciao", BLUE, I), ("♥", BLUE, ""), ("Hallo", ORANGE, B)],
    [("Olá", CYAN, B), ("✕", CYAN, ""), ("Hei", BROWN, ""), ("⌕", BROWN, ""), ("Aloha", PINK, I), ("&", PINK, B), ("Salut", CYAN, B), ("✓", VIOLET, B)],
    [("Moi", VIOLET, B), ("⌘", YELLOW, ""), ("Salve", GREEN, ""), ("⚠", GREEN, ""), ("Halo", MAGENTA, B), ("⇧", MAGENTA, B), ("Servus", RED, B)],
    [("Hoi", TEAL, ""), ("⌥", TEAL, ""), ("Szia", BLUE, B), ("→", BLUE, B), ("Merhaba", ORANGE, B), ("⏎", ORANGE, ""), ("Tere", YELLOW, I)],
    [("Bok", BROWN, B), ("§", BROWN, B), ("Bonjour", PINK, B), ("❯", PINK, ""), ("Ahoj", CYAN, I), ("#", CYAN, ""), ("Hej!", VIOLET, "")],
]


def paint(text, colour, style=""):
    r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return f"{style}\x1b[38;2;{r};{g};{b}m{text}{R}"


def greetings_text():
    return "\n".join(" ".join(paint(*part) for part in row) for row in GREETINGS) + "\n"


def code_text():
    key, name, kind, comment = (lambda x: paint(x, VIOLET)), (lambda x: paint(x, BLUE, B)), (lambda x: paint(x, TEAL)), (lambda x: paint(x, GREY, I))
    text = lambda x: paint('"%s"' % x, PINK)  # noqa: E731
    hellos = ", ".join(text(h) for h in ("Hello", "Hola", "Ciao", "Bonjour"))
    lines = [
        comment("// greet everyone, one at a time"),
        "%s %s(names: &[&%s]) -> %s<%s> {" % (key("fn"), name("greet"), kind("str"), kind("Vec"), kind("String")),
        "    %s hellos = [%s];" % (key("let"), hellos),
        "    names.iter()",
        "        .zip(hellos)",
        "        .map(|(name, hi)| %s(%s))" % (paint("format!", ORANGE, B), text("{hi}, {name}!")),
        "        .collect()",
        "}",
    ]
    return "\n".join(lines) + "\n"


def hello():
    """Greetings and code on one sheet. Drawn well over twice the size it is shown at, so it is sharp on a Retina display."""
    from . import eyes

    fonts, tmp = ROOT / "fonts", Path(tempfile.gettempdir())
    paper, ink = eyes.BG, eyes.FG
    eyes.BG, eyes.FG = PAPER, INK
    try:
        parts = [
            Image.open(render(greetings_text(), tmp / "allomono-hello-1.png", fonts / "allomono-Regular.ttf", fonts / "allomono-Bold.ttf", size=26, scale=4)[0]).convert("RGB"),
            Image.open(render(code_text(), tmp / "allomono-hello-2.png", fonts / "allomono-Regular.ttf", fonts / "allomono-Bold.ttf", size=13, scale=4)[0]).convert("RGB"),
        ]
    finally:
        eyes.BG, eyes.FG = paper, ink
    margin, gap = 192, 144
    width = max(im.width for im in parts) + 2 * margin
    sheet = Image.new("RGB", (width, sum(im.height for im in parts) + gap + 2 * margin), PAPER)
    y = margin
    for im in parts:
        sheet.paste(im, (margin, y))
        y += im.height + gap
    out = ROOT / "docs" / "hello.png"
    out.parent.mkdir(exist_ok=True)
    sheet.save(out)
    print("%s  (%dx%d)" % ((out.relative_to(ROOT),) + sheet.size))


def characters():
    fonts = ROOT / "fonts"
    tmp = Path(tempfile.gettempdir())
    images = []
    for i, (size, text) in enumerate(BLOCKS):
        out, _, _ = render(text + "\n", tmp / ("allomono-specimen-%d.png" % i), fonts / "allomono-Regular.ttf", fonts / "allomono-Bold.ttf", size=size, scale=2, pad=int(size * 0.9))
        images.append(Image.open(out).convert("RGB"))
    margin = 40
    width = max(im.width for im in images) + 2 * margin
    sheet = Image.new("RGB", (width, sum(im.height for im in images) + 2 * margin), BG)
    y = margin
    for im in images:
        sheet.paste(im, (margin, y))
        y += im.height
    out = ROOT / "docs" / "characters.png"
    sheet.save(out)
    print("%s  (%dx%d)" % ((out.relative_to(ROOT),) + sheet.size))


def stamp_readme():
    """GitHub serves README images from a cache keyed on the file's path, and
    goes on showing an old picture for a while after a new one is pushed. So
    each picture's file name carries a short fingerprint of its contents: a
    new picture is a new file, and can never be confused with the old one."""
    docs, readme = ROOT / "docs", ROOT / "README.md"
    text = readme.read_text()
    for name in ("hello", "characters"):
        fresh = docs / (name + ".png")
        mark = hashlib.sha256(fresh.read_bytes()).hexdigest()[:8]
        for old in docs.glob(name + "-*.png"):
            old.unlink()
        fresh.rename(docs / ("%s-%s.png" % (name, mark)))
        text = re.sub(r"docs/%s(-[0-9a-f]+)?\.png" % name, "docs/%s-%s.png" % (name, mark), text)
    readme.write_text(text)


if __name__ == "__main__":
    hello()
    characters()
    stamp_readme()
