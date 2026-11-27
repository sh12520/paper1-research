"""Prepare four-page visual proof sheets from actual rendered pages."""

from pathlib import Path
import argparse
import re

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages",type=Path)
    args = parser.parse_args()
    def sequence(path):
        return int(re.search(r"(\d+)$",path.stem).group(1))
    pages = sorted(args.pages.glob("page-*.png"),key=sequence)
    if not pages:
        raise RuntimeError("No real per-page render")
    for start in range(0,len(pages),4):
        canvas = Image.new("RGB",(1480,2035),"#e9edf3")
        draw = ImageDraw.Draw(canvas)
        for index,path in enumerate(pages[start:start+4]):
            left = (index%2)*740 + 20
            top = (index//2)*1015 + 21
            with Image.open(path) as page:
                pic = page.convert("RGB")
                pic.thumbnail((700,965),Image.Resampling.LANCZOS)
                canvas.paste(pic,(left+(700-pic.width)//2,top+19))
            draw.text((left,top-3),f"PAGE {sequence(path)}",fill="#293848")
        canvas.save(args.pages/f"board-{start//4+1:02d}.png")


if __name__=="__main__":
    main()
