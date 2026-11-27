"""Render the unmodified Word file with the isolated local Writer/Poppler toolchain."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from AUTO_PAPER_72H import DELIVERY, WORK
from build_manuscript import BASE


def render(docx,output):
    profile = Path(os.environ["USERPROFILE"])
    local = Path(os.environ["LOCALAPPDATA"])
    installer_image = local/"CSODSResearchTools/LibreOffice-26.8.3-portable-extract/program_files/program"
    if not (installer_image/"soffice.exe").exists():
        raise RuntimeError("Missing locally validated LibreOffice renderer")
    render_docx = profile/(".codex/plugins/cache/openai-primary-runtime/documents/"
                           "26.1116.12010/skills/documents/render_docx.py")
    if not render_docx.is_file() or not shutil.which("pdftoppm"):
        raise RuntimeError("Missing document renderer or Poppler")
    env = os.environ.copy()
    env["PATH"]=str(installer_image)+os.pathsep+env.get("PATH","")
    subprocess.run([sys.executable,"-B",str(render_docx),str(docx),"--output_dir",str(output),
                    "--dpi","124","--emit_pdf"],env=env,check=True,timeout=180)


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx",type=Path,default=DELIVERY/(BASE+".docx"))
    parser.add_argument("--output",type=Path,default=WORK/"word_layout")
    args = parser.parse_args()
    render(args.docx.resolve(strict=True),args.output.resolve())
