"""Export the Chinese Markdown paper through Pandoc with a readable A4 reference."""
from pathlib import Path
import argparse
import re
import subprocess
import tempfile

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


def set_style(doc, name, *, size, east_asian, bold=False, keep=False, before=0, after=0):
    styles = doc.styles
    if name not in styles:
        styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    style = styles[name]
    style.font.name = "Times New Roman"
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor.from_string("000000")
    fonts = style.element.get_or_add_rPr().rFonts
    fonts.set(qn("w:eastAsia"), east_asian)
    fmt = style.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.keep_with_next = keep
    for border in style.element.xpath("./w:pPr/w:pBdr"):
        border.getparent().remove(border)
    return style


def reference_file(path):
    with path.open("wb") as out:
        subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"], stdout=out, check=True)
    doc = Document(path)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.3)
    sec.top_margin = sec.bottom_margin = Cm(2.15)
    base = set_style(doc, "Normal", size=11, east_asian="SimSun", after=5)
    base.paragraph_format.line_spacing = 1.31
    set_style(doc, "Body Text", size=11, east_asian="SimSun", after=5)
    title = set_style(doc, "Title", size=20, east_asian="SimHei", bold=True, keep=True, after=15)
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_style(doc, "Heading 1", size=15, east_asian="SimHei", bold=True, keep=True, before=14, after=6)
    set_style(doc, "Heading 2", size=13, east_asian="SimHei", bold=True, keep=True, before=11, after=5)
    set_style(doc, "Heading 3", size=11.5, east_asian="SimHei", bold=True, keep=True, before=10, after=5)
    for name in ("Caption", "Image Caption", "Table Caption", "Figure Caption"):
        st = set_style(doc, name, size=10, east_asian="SimSun", before=3, after=8)
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for name in ("Figure", "Captioned Figure"):
        st = set_style(doc, name, size=10, east_asian="SimSun", keep=True, before=5)
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_style(doc, "RDINP References", size=10, east_asian="SimSun", after=3)
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    page_field = OxmlElement("w:fldSimple")
    page_field.set(qn("w:instr"), "PAGE")
    footer._p.append(page_field)
    doc.save(path)


def set_table_style(table):
    props = table._tbl.tblPr
    for item in props.xpath("./w:tblBorders"):
        props.remove(item)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = OxmlElement("w:" + edge)
        for k, text in {"val": "single", "sz": "4", "color": "D9D9D9"}.items():
            border.set(qn("w:" + k), text)
        borders.append(border)
    props.append(borders)
    for i, row in enumerate(table.rows):
        trpr = row._tr.get_or_add_trPr()
        trpr.append(OxmlElement("w:cantSplit"))
        if i == 0:
            trpr.append(OxmlElement("w:tblHeader"))
        for cell in row.cells:
            if i == 0:
                shade = OxmlElement("w:shd")
                shade.set(qn("w:fill"), "EBF0F3")
                cell._tc.get_or_add_tcPr().append(shade)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = i < len(table.rows) - 1
                paragraph.paragraph_format.space_before = Pt(4)
                paragraph.paragraph_format.space_after = Pt(4)
                for run in paragraph.runs:
                    run.font.size = Pt(10)
                    if i == 0:
                        run.bold = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    opts = parser.parse_args()
    markdown, output = opts.markdown.resolve(), opts.out.resolve()
    with tempfile.TemporaryDirectory(prefix="rdinp-reference-") as temp:
        style = Path(temp) / "reference.docx"
        reference_file(style)
        subprocess.run(
            ["pandoc", "--from=markdown+tex_math_dollars+implicit_figures",
             "--reference-doc", str(style), str(markdown), "-o", str(output)],
            cwd=markdown.parent, check=True,
        )
    doc = Document(output)
    for table in doc.tables:
        set_table_style(table)
    for paragraph in doc.paragraphs:
        if re.match(r"^\[\d+\] ", paragraph.text):
            paragraph.style = "RDINP References"
    doc.save(output)


if __name__ == "__main__":
    main()
