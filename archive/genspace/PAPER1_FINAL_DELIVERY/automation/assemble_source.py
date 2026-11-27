"""Assemble a numbered, citeproc-ready version from manuscript sections."""

import argparse
from pathlib import Path
import re

from AUTO_PAPER_72H import WORK, atomic
from build_manuscript import TITLE, ENGLISH

SECTIONS = ("front.md", "introduction_related.md", "model_method_theory.md",
            "evaluation.md", "discussion_conclusion.md")
FIGURE_ONE = ("![图 1　CS-ODS 的公开合同搜索、独立核验和双边协商。公开阶段按语法生成骨架，"
              "用状态—时间—资源包络计算下界，经模板归并、配置赋值形成有序流。"
              "独立裁判复核覆盖，私有偏好在协商侧参与接受判断。]"
              "(PAPER1_FIGURES/fig01_csods_workflow.png){width=91%}")


def assemble(destination):
    pieces = [f'---\ntitle: "{TITLE}"\nsubtitle: "{ENGLISH}"\nlang: zh-CN\n---']
    for name in SECTIONS:
        value = (WORK/name).read_text(encoding="utf-8-sig").strip()
        if name == "model_method_theory.md":
            value = value.replace("### 4.1 状态–时间–资源包络",
                                  "图 1 展示公开搜索前沿、覆盖裁判与双边协议之间的接口。\n\n" +
                                  FIGURE_ONE + "\n\n### 4.1 状态–时间–资源包络",1)
        elif name=="evaluation.md":
            value = value.replace("## 实验评价", "## 6 实验评价",1)
            labels = iter(range(1,14))
            value = re.sub(r"(?m)^### (?!\d)(.+)$",lambda m:f"### 6.{next(labels)} {m[1]}",value)
        pieces.append(value)
    atomic(destination,"\n\n".join(pieces)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path)
    assemble(p.parse_args().output.resolve())
