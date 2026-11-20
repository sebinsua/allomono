"""Render proof sheets from a built font: `python -m allomono.proof [font ...]`.

Text is set by FreeType through Pillow, from the .ttf an editor would load.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BG, INK, RULE = "#ffffff", "#111111", "#e6e6e6"

SAMPLE = [
    "abcdefghijklm",
    "nopqrstuvwxyz",
    "ABCDEFGHIJKLM",
    "NOPQRSTUVWXYZ",
    "0123456789",
    "(){}[]<>/\\|!?",
    ".,:;'\"`-_=+*~^",
    "#$%&@ Il1 O0o",
]

SYMBOLS = [
    "\u2190\u2192\u2191\u2193\u2194\u2195\u2196\u2197\u2198\u2199\u21d0\u21d2\u21d4",
    "\u21a9\u21b5\u21bb\u21ba\u2318\u2325\u21e7\u2303\u238b\u21e5\u232b\u2326\u23ce",
    "\u2423\u2315\u25cf\u25cb\u25a0\u25a1\u25b2\u25bc\u25b6\u25c0\u25c6\u2605\u2665",
    "\u26a0\u2713\u2715\u2717\u276e\u276f\u221e\u2030\u2116\u2103\u2109\u00bd\u00be",
    "\u00e9\u00df\u00f8\u00f1\u00e7\u017e\u00e5\u00fe\u00ed\u012f\u013a\u0142\u0133",
    "\u00c9\u00d8\u00d1\u00c7\u017d\u00c5\u00de\u00cd\u012e\u0139\u0141\u0132\u00c6",
    "\u00e6\u0153\u0152\u2014\u2013\u2026\u201c\u201d\u2018\u2019\u00ab\u00bb\u00b7",
    "$\u00a2\u00a3\u00a5\u20ac\u20b9\u20a9\u20bd\u20bf\u00b1\u00d7\u00f7\u2260",
]

WORDS = [
    "Hello Hola Ciao",
    "Bonjour Salut 42",
    "jelly fig Quartz",
]

CODE = [
    "fn word_counts(text: &str) -> HashMap<&str, usize> {",
    "    let mut counts = HashMap::new();",
    "    for word in text.split_whitespace() {",
    "        *counts.entry(word).or_insert(0) += 1;",
    "    }",
    "    counts",
    "}",
    "",
    "illicit minimum William MMWW fjord ruffle",
    "The quick brown fox jumps over the lazy dog.",
]


def sheet(font_path, out_path, sizes, lines, line_height=1.21, cells=False, index=0):
    pad = 60
    blocks, width = [], 0
    for size in sizes:
        font = ImageFont.truetype(str(font_path), size, index=index)
        adv = font.getlength("n")
        blocks.append((size, font, adv, int(len(lines) * size * line_height)))
        width = max(width, int(adv * max(len(l) for l in lines)))
    img = Image.new("RGB", (width + 2 * pad, sum(b[3] for b in blocks) + pad * (len(blocks) + 1)), BG)
    d = ImageDraw.Draw(img)
    y = pad
    for size, font, adv, h in blocks:
        if cells:
            for i in range(max(len(l) for l in lines) + 1):
                x = pad + i * adv
                d.line([(x, y), (x, y + h)], fill=RULE)
        for i, line in enumerate(lines):
            d.text((pad, y + i * size * line_height), line, font=font, fill=INK)
        y += h + pad
    img.save(out_path)
    return out_path


BOXES = """\
\u256d\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256e  \u250c\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2510  \u250f\u2501\u2501\u2501\u2533\u2501\u2501\u2501\u2513  \u2554\u2550\u2550\u2550\u2566\u2550\u2550\u2550\u2557  \u2552\u2550\u2550\u2564\u2550\u2550\u2555 \u2553\u2500\u2500\u2565\u2500\u2500\u2556
\u2502 \u25cf read       \u2502 \u2713 done    \u2502  \u2502 a \u2502 b \u2502  \u2503 a \u2503 b \u2503  \u2551 a \u2551 b \u2551  \u2502  \u2502  \u2502 \u2551  \u2551  \u2551
\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524  \u251c\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524  \u2523\u2501\u2501\u2501\u254b\u2501\u2501\u2501\u252b  \u2560\u2550\u2550\u2550\u256c\u2550\u2550\u2550\u2563  \u255e\u2550\u2550\u256a\u2550\u2550\u2561 \u255f\u2500\u2500\u256b\u2500\u2500\u2562
\u2502 \u25cb edit       \u2502 \u2717 failed  \u2502  \u2502 c \u2502 d \u2502  \u2503 c \u2503 d \u2503  \u2551 c \u2551 d \u2551  \u2502  \u2502  \u2502 \u2551  \u2551  \u2551
\u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256f  \u2514\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2518  \u2517\u2501\u2501\u2501\u253b\u2501\u2501\u2501\u251b  \u255a\u2550\u2550\u2550\u2569\u2550\u2550\u2550\u255d  \u2558\u2550\u2550\u2567\u2550\u2550\u255b \u2559\u2500\u2500\u2568\u2500\u2500\u255c
\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588 \u2591\u2592\u2593\u2588 \u258f\u258e\u258d\u258c\u258b\u258a\u2589\u2588 \u2596\u2597\u2598\u2599\u259a\u259b\u259c\u259d\u259e\u259f \u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f \u28ff  \u2574\u2575\u2576\u2577 \u257c\u257d\u257e\u257f \u2571\u2572\u2573 \u2504\u2505\u2506\u2507\u254c\u254d\u254e\u254f  \u23bf out
"""


def boxes(out):
    """Box drawing has to be seen on a terminal's grid, where the pieces must join: drawn by eyes.py (macOS)."""
    try:
        from .eyes import render
    except ImportError:
        return None
    fonts = ROOT / "fonts"
    return render(BOXES, out, fonts / "allomono-Regular.ttf", fonts / "allomono-Bold.ttf", size=13, scale=4, pad=30)[0]


if __name__ == "__main__":
    out = ROOT / "proofs"
    out.mkdir(exist_ok=True)
    fonts = [Path(a) for a in sys.argv[1:]] or sorted((ROOT / "fonts").glob("allomono-*.ttf"))
    print(boxes(out / "boxes.png"))
    for font in fonts:
        print(sheet(font, out / (font.stem + "-glyphs.png"), (110,), SAMPLE, line_height=1.35, cells=True))
        print(sheet(font, out / (font.stem + "-code.png"), (44, 26, 16), CODE))
        print(sheet(font, out / (font.stem + "-symbols.png"), (110,), SYMBOLS, line_height=1.35, cells=True))
        print(sheet(font, out / (font.stem + "-words.png"), (150,), WORDS, line_height=1.1))
