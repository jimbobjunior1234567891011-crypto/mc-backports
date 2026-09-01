"""Render docs/logo.png.

The letterforms are drawn here by hand in the 5x7 pixel style Minecraft's default font
uses, rather than lifted from the game's font atlas - the shapes are ours, so the image
can live in a public repo without redistributing Mojang assets. Rendering rules follow
the game's text: hard pixel edges, and a shadow offset one pixel down-right in a darker
shade of the same colour.

    python tools/make_logo.py
"""
import os

from PIL import Image

SCALE = 14
GAP = 2                       # blank column between glyphs, like the game's font
SPACE_ADVANCE = 4
TEXT = "MC BACKPORTS"
FG = (255, 170, 0, 255)       # the game's gold
SHADOW = (63, 42, 0, 255)     # gold at 25%, the same relationship vanilla uses
PAD = 3                       # in pixels, before scaling

GLYPHS = {
    "A": [".###.",
          "#...#",
          "#...#",
          "#####",
          "#...#",
          "#...#",
          "#...#"],
    "B": ["####.",
          "#...#",
          "#...#",
          "####.",
          "#...#",
          "#...#",
          "####."],
    "C": [".###.",
          "#...#",
          "#....",
          "#....",
          "#....",
          "#...#",
          ".###."],
    "K": ["#...#",
          "#..#.",
          "#.#..",
          "##...",
          "#.#..",
          "#..#.",
          "#...#"],
    "M": ["#...#",
          "##.##",
          "#.#.#",
          "#...#",
          "#...#",
          "#...#",
          "#...#"],
    "O": [".###.",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          ".###."],
    "P": ["####.",
          "#...#",
          "#...#",
          "####.",
          "#....",
          "#....",
          "#...."],
    "R": ["####.",
          "#...#",
          "#...#",
          "####.",
          "#.#..",
          "#..#.",
          "#...#"],
    "S": [".####",
          "#....",
          "#....",
          ".###.",
          "....#",
          "....#",
          "####."],
    "T": ["#####",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          "..#.."],
}

GLYPH_H = 7


def advance(ch):
    return SPACE_ADVANCE if ch == " " else len(GLYPHS[ch][0]) + GAP


def draw(image, text, ox, oy, colour):
    pen = ox
    for ch in text:
        if ch == " ":
            pen += SPACE_ADVANCE
            continue
        rows = GLYPHS[ch]
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                if cell == "#":
                    image.putpixel((pen + x, oy + y), colour)
        pen += len(rows[0]) + GAP


def main():
    width = sum(advance(ch) for ch in TEXT) - GAP + 1 + PAD * 2
    height = GLYPH_H + 1 + PAD * 2
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    draw(image, TEXT, PAD + 1, PAD + 1, SHADOW)      # shadow first, down-right by one
    draw(image, TEXT, PAD, PAD, FG)

    image = image.resize((width * SCALE, height * SCALE), Image.NEAREST)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "logo.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    image.save(out)
    print("wrote", out, image.size)


if __name__ == "__main__":
    main()
