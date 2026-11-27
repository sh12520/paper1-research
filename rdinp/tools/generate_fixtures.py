"""Generate reproducible test patterns for the local experiment runners."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    palettes = [
        ("camera.png", (26, 43, 79), (230, 180, 70)),
        ("astronaut.png", (72, 33, 68), (60, 202, 181)),
        ("coffee.png", (51, 42, 33), (221, 139, 164)),
    ]
    for index, (name, dark, bright) in enumerate(palettes):
        image = Image.new("RGB", (192, 192), color=dark)
        draw = ImageDraw.Draw(image)
        for y in range(12, 181, 24):
            for x in range(12, 181, 24):
                if (x // 24 + (index + 1) * (y // 24)) % 3 == 0:
                    draw.rectangle((x - 7, y - 7, x + 7, y + 7), fill=bright)
        radius = 20 + 5 * index
        draw.ellipse((96 - radius, 96 - radius, 96 + radius, 96 + radius), outline=bright, width=4)
        image.save(output / name, format="PNG")
    print("Generated fixture patterns:", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    generate(parser.parse_args().out)

