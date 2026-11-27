"""Check references, frozen evidence, equations, embedded graphics and exports."""

from collections import Counter
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
from zipfile import ZipFile

from docx import Document
from lxml import etree
from PIL import Image
from pypdf import PdfReader

from AUTO_PAPER_72H import DELIVERY, ROOT, WORK, atomic, sha
from build_manuscript import BASE, TITLE, ENGLISH


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def nodes(value):
    if isinstance(value,dict):
        if "t" in value and "c" in value:
            yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value,list):
        for child in value:
            yield from nodes(child)


def compact(text):
    return re.sub(r"\s+", "", text)


def main():
    source = WORK/"manuscript_final_source.md"
    manuscript = DELIVERY/(BASE+".md")
    docx = DELIVERY/(BASE+".docx")
    pdf = DELIVERY/(BASE+".pdf")
    refs = DELIVERY/"PAPER1_REFERENCES.bib"
    pandoc = shutil.which("pandoc")
    require(pandoc is not None,"Missing Pandoc for reference/structure checks")
    ast = json.loads(subprocess.check_output([pandoc,str(source),"--from=markdown","--to=json"],
                                             cwd=DELIVERY,timeout=50))
    items = list(nodes(ast))
    cited = {entry["citationId"] for item in items if item["t"]=="Cite" for entry in item["c"][0]}
    bibliography = json.loads(subprocess.check_output([pandoc,str(refs),"--from=biblatex","--to=csljson"],
                                                      cwd=DELIVERY,timeout=50))
    ref_keys = {r["id"] for r in bibliography}
    require(ref_keys==cited and len(ref_keys)==len(bibliography),"Missing, duplicate or unused citation")
    checked = [pandoc,str(source),"--citeproc","--bibliography",str(refs),"--csl",
               str(Path(__file__).parent/"ieee.csl"),"--fail-if-warnings","--to=html5","--mathml"]
    subprocess.run(checked,cwd=DELIVERY,stdout=subprocess.DEVNULL,timeout=50,check=True)
    math_nodes = sum(item["t"]=="Math" for item in items)
    images = [item["c"][-1][0] for item in items if item["t"]=="Image"]
    require(len(images)==len(set(images))==6,"Expected six unique manuscript figures")
    for rel in images:
        path = DELIVERY/rel
        with Image.open(path) as bmp:
            require(bmp.width>=1000 and bmp.height>=600,"Insufficient PNG resolution in "+rel)
            bmp.verify()
        require(len(PdfReader(path.with_suffix(".pdf")).pages)==1,"Vector counterpart not readable "+rel)
    with ZipFile(docx) as package:
        namespace = {"m":"http://schemas.openxmlformats.org/officeDocument/2006/math",
                     "w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        main_xml = etree.fromstring(package.read("word/document.xml"))
        native_math = len(main_xml.xpath("//m:oMath",namespaces=namespace))
        media = [p for p in package.namelist() if p.startswith("word/media/")]
        require(native_math==math_nodes,"Editable Word math count differs from manuscript")
        require(len(media)==6,"Word images missing")
    word = Document(str(docx))
    word_text = "\n".join(p.text for p in word.paragraphs)
    reader = PdfReader(pdf)
    pages = [page.extract_text() for page in reader.pages]
    pdf_text = "\n".join(pages)
    require(len(pages)>=8 and all(len(compact(page))>=16 for page in pages),"Unexpected empty or short PDF page")
    md = manuscript.read_text(encoding="utf-8")
    for tag,text in (("Word",word_text),("PDF",pdf_text),("Markdown",md)):
        joined = compact(text)
        for marker in (TITLE,ENGLISH,"24/24","92/96","2.57","参考文献"):
            require(compact(marker) in joined,f"Missing {marker} in {tag}")
        require("[@" not in text,"Unprocessed citation keys in "+tag)
    require("INDEPENDENT_CONFIRMATION" in md and "DEVELOPMENT" in md,"Evidence classifications absent")
    require(all(re.search(r"图\s*"+str(i)+r"(?!\d)",word_text) and
                re.search(r"图\s*"+str(i)+r"(?!\d)",pdf_text) for i in range(1,7)),
            "Expected numbered figure captions missing")
    with (ROOT/"results/depth3_proof/per_query.csv").open(encoding="utf-8",newline="") as stream:
        archived = list(csv.DictReader(stream))
    statuses = Counter(row["k"+str(k)] for row in archived for k in (10,100,500))
    require(len(archived)==24 and statuses=={"EXACT_TOPK_FULL_LENGTH":62,"EXACT_DOMAIN_EXHAUSTED_SHORT":10},
            "Depth 3 proof figures do not match archived fixture panel")
    with (DELIVERY/"PAPER1_TABLES/source_sha256.csv").open(encoding="utf-8-sig",newline="") as stream:
        digest_rows = list(csv.DictReader(stream))
    for row in digest_rows:
        source_file = row.get("path") or row.get("relative_path") or row.get("source_path")
        require(source_file is not None and sha(ROOT/source_file)==row["sha256"],"Figure data-source digest changed")
    evidence = {"status":"PASS","manifest_sha256":sha(ROOT/"METHOD_FINAL_FREEZE_MANIFEST.json"),
                "correctness_scope":"development artifacts, no confirmation results",
                "word_native_equations":native_math,"references_cited_and_parsed":len(cited),
                "numbered_figures":len(images),"pdf_pages":len(pages),
                "pdf_text_characters_by_page":[len(p) for p in pages],
                "depth3_independent_checkpoint_statuses":statuses,
                "figure_sources_verified":len(digest_rows),
                "export_sha256_by_file":{p.name:sha(p) for p in (manuscript,docx,pdf)}}
    atomic(WORK/"mechanical_qa.json",json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(json.dumps(evidence,ensure_ascii=False))


if __name__=="__main__":
    main()
