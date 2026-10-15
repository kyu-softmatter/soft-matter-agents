"""Draw autofocus.ico (a focus reticle over a particle) for the desktop launcher.

    python tools/launcher/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

S = 256
OUT = Path(__file__).with_name("autofocus.ico")


def main() -> None:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, S - 8, S - 8), radius=48, fill="#0b0b0b")
    d.ellipse((96, 96, 160, 160), fill="#3fd17a")  # the particle, GREEN light
    d.ellipse((52, 52, S - 52, S - 52), outline="#2a78d6", width=12)
    for a, b in (((128, 30), (128, 74)), ((128, 182), (128, 226)),
                 ((30, 128), (74, 128)), ((182, 128), (226, 128))):
        d.line((a, b), fill="#eb6834", width=12)
    im.save(OUT, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(OUT)


if __name__ == "__main__":
    main()
