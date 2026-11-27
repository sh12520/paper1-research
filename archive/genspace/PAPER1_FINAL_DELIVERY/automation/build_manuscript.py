"""Build editable Word and matching PDF/Markdown from the revised manuscript."""

from pathlib import Path
import argparse
import os
import re
import shutil
import subprocess
import tempfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from AUTO_PAPER_72H import DELIVERY, WORK, atomic

HERE = Path(__file__).resolve().parent
BASE = "PAPER1_FINAL_FOR_HUMAN_REVIEW"
TITLE = "面向6G智能体通信意图协商的能力语义约束按需合同合成方法"
ENGLISH = "Capability-Semantic On-Demand Contract Synthesis for Agentic Communication-Intent Negotiation in 6G Networks"


def style_font(style, latin, southeast, size, *, weight=None):
    style.font.name = latin
    style.font.size = Pt(size)
    if weight is not None:
        style.font.bold = weight
    style.font.color.rgb = RGBColor.from_string("161E28")
    style.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"),southeast)


def reference(pandoc, target):
    with target.open("wb") as stream:
        subprocess.run([pandoc,"--print-default-data-file","reference.docx"],stdout=stream,check=True,timeout=25)
    doc = Document(str(target))
    styles = doc.styles
    style_font(styles["Normal"],"Cambria","SimSun",11)
    text_language = styles["Normal"].element.get_or_add_rPr().find(qn("w:lang"))
    if text_language is None:
        text_language = OxmlElement("w:lang")
        styles["Normal"].element.get_or_add_rPr().append(text_language)
    text_language.set(qn("w:eastAsia"),"zh-CN")
    p = styles["Normal"].paragraph_format
    p.line_spacing = 1.24
    p.space_after = Pt(6)
    p.widow_control = True
    style_font(styles["Body Text"],"Cambria","SimSun",11)
    styles["Body Text"].paragraph_format.line_spacing = 1.24
    style_font(styles["Title"],"Cambria","Microsoft YaHei",16,weight=True)
    styles["Title"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    styles["Title"].paragraph_format.space_after = Pt(8)
    style_font(styles["Subtitle"],"Cambria","Microsoft YaHei",12)
    styles["Subtitle"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    styles["Subtitle"].paragraph_format.space_after = Pt(16)
    for level,size in ((1,14),(2,13),(3,11.5)):
        style = styles[f"Heading {level}"]
        style_font(style,"Cambria","Microsoft YaHei",size,weight=True)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.space_before = Pt(14 if level<3 else 10)
        style.paragraph_format.space_after = Pt(6)
    for label,size in (("Caption",9.5),("Bibliography",10),("Source Code",9)):
        if label in styles:
            style_font(styles[label],"Consolas" if label=="Source Code" else "Cambria","SimSun",size)
    doc.save(str(target))


def polish(in_docx, out_docx):
    doc = Document(str(in_docx))
    doc.core_properties.title = TITLE
    doc.core_properties.subject = "Capability-semantic contract synthesis and certified search"
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    for section in doc.sections:
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.top_margin = Mm(23)
        section.bottom_margin = Mm(22)
        section.left_margin = Mm(23)
        section.right_margin = Mm(23)
        section.footer_distance = Mm(10)
    for table in doc.tables:
        if len(table.rows):
            header = table.rows[0]._tr.get_or_add_trPr()
            header.append(OxmlElement("w:tblHeader"))
        for row in table.rows:
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = Pt(3)
                    paragraph.paragraph_format.space_before = Pt(2)
                    paragraph.paragraph_format.line_spacing = 1.10
                    for run in paragraph.runs:
                        run.font.size = Pt(9.5)
    introduction = False
    for paragraph in doc.paragraphs:
        introduction = introduction or paragraph.text.startswith("1 引言")
        if not introduction and paragraph.style.name in ("First Paragraph","Body Text"):
            paragraph.paragraph_format.line_spacing = 1.10
            paragraph.paragraph_format.space_after = Pt(4)
        if paragraph.style.name == "Source Code":
            paragraph.paragraph_format.keep_together = True
            paragraph.paragraph_format.line_spacing = 1.03
        if paragraph.text.startswith("算法 1"):
            paragraph.paragraph_format.keep_with_next = True
        if paragraph._p.xpath(".//w:drawing"):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.keep_with_next = True
        if paragraph.style.name in ("Image Caption","Caption","Table Caption"):
            paragraph.paragraph_format.keep_together = True
            paragraph.paragraph_format.space_after = Pt(9)
    footer = doc.sections[0].footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"),"PAGE")
    footer._p.append(field)
    doc.save(str(out_docx))


def render_pdf(pandoc, source, options, temp, output):
    html = temp/"manuscript.html"
    staged_pdf = temp/"final.pdf"
    subprocess.run([pandoc,str(source),*options,"--to=html5","--standalone","--mathml",
                    "--embed-resources","--css",str(HERE/"print.css"),"--output",str(html)],
                   check=True,cwd=DELIVERY,timeout=85)
    markup = html.read_text(encoding="utf-8")
    markup = re.sub(r'(\b(?:xml:)?lang)="en-US"',r'\1="zh-CN"',markup,count=2)
    html.write_text(markup,encoding="utf-8")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node and Playwright are required for PDF export")
    subprocess.run([node,str(HERE/"render_html_pdf.js"),str(html),str(staged_pdf)],
                   check=True,cwd=DELIVERY,timeout=95)
    os.replace(staged_pdf,output)


def render(source, directory, stem, *, only_pdf=False):
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError("Pandoc is required to generate the paper")
    options = ["--from=markdown+tex_math_dollars+link_attributes+fenced_divs",
               "--citeproc","--bibliography",str(DELIVERY/"PAPER1_REFERENCES.bib"),
               "--csl",str(HERE/"ieee.csl"),"--metadata","reference-section-title=参考文献",
               "--metadata","link-citations=true","--resource-path",str(DELIVERY)]
    directory.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="manuscript-",dir=WORK,ignore_cleanup_errors=True) as tmp:
        temp = Path(tmp)
        ref = temp/"reference.docx"
        draft = temp/"before_layout.docx"
        final_word = temp/"final.docx"
        if not only_pdf:
            reference(pandoc,ref)
            subprocess.run([pandoc,str(source),*options,"--to=docx","--reference-doc",str(ref),
                            "--output",str(draft)],check=True,cwd=DELIVERY,timeout=80)
            polish(draft,final_word)
            md = subprocess.check_output([pandoc,str(source),*options,"--to=markdown-smart","--wrap=none"],
                                         cwd=DELIVERY,timeout=45).decode("utf-8")
            atomic(directory/(stem+".md"),f"# {TITLE}\n\n**{ENGLISH}**\n\n"+md)
            os.replace(final_word,directory/(stem+".docx"))
        render_pdf(pandoc,source,options,temp,directory/(stem+".pdf"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview",type=Path,help="Compile a draft in the internal proofing folder")
    parser.add_argument("--pdf-only",action="store_true")
    args = parser.parse_args()
    render(args.preview.resolve() if args.preview else WORK/"manuscript_final_source.md",
           WORK if args.preview else DELIVERY, "manuscript_preview" if args.preview else BASE,
           only_pdf=args.pdf_only)


if __name__=="__main__":
    main()
