"""Render the workflow described by the frozen DepthCursor and protocol adapter."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


TARGET = Path(__file__).resolve().parents[1] / "PAPER1_FIGURES"
INK = "#12273e"
EDGE = "#5a738c"
ACCENT = "#1b675e"


def box(ax,x,y,w,h,title,detail,*,face="#eaf0f6", edge=EDGE):
    patch = FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.012,rounding_size=0.022",
                           linewidth=1.05,facecolor=face,edgecolor=edge)
    ax.add_patch(patch)
    ax.text(x+w/2,y+h*.67,title,ha="center",va="center",fontsize=9.2,weight="semibold",color=INK)
    ax.text(x+w/2,y+h*.32,detail,ha="center",va="center",fontsize=7.5,linespacing=1.27,color=INK)


def arrow(ax,a,b,*,dashed=False):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle="-|>",mutation_scale=10,color=EDGE,
                                 lw=1.0,linestyle="--" if dashed else "-",shrinkA=1,shrinkB=1))


def main():
    plt.rcParams.update({"font.family":"DejaVu Sans","pdf.fonttype":42,"savefig.facecolor":"white"})
    fig,ax=plt.subplots(figsize=(7.08,4.7))
    fig.subplots_adjust(left=.02,right=.98,bottom=.02,top=.97)
    ax.set_xlim(0,1)
    ax.set_ylim(0,1)
    ax.axis("off")
    ax.text(.04,.97,"PUBLIC CONTRACT SEARCH",ha="left",va="center",weight="semibold",fontsize=8.6,color=ACCENT)
    box(ax,.04,.744,.27,.155,"Typed contract DSL","Static, If, Sequence\nDelay, ValidFor, Offload")
    box(ax,.365,.744,.27,.155,"Public query","Capabilities, profiles\nRAN / FH / EDGE capacities")
    box(ax,.69,.744,.27,.155,"Six-cell envelope","State × time coverage\nAdmissible public-score bound")
    arrow(ax,(.315,.823),(.36,.823))
    arrow(ax,(.64,.823),(.685,.823))
    box(ax,.04,.482,.27,.155,"Shape frontier","Expand eligible\nconstructors lazily")
    box(ax,.365,.482,.27,.155,"Semantic templates","Normalize and merge\nKeep witness contexts")
    box(ax,.69,.482,.27,.155,"Assignment frontier","Bind profiles lazily\nScore completed keys")
    ax.plot([.825,.825,.175],[.735,.690,.690],color=EDGE,lw=1)
    arrow(ax,(.175,.690),(.175,.645))
    arrow(ax,(.315,.562),(.36,.562))
    arrow(ax,(.64,.562),(.685,.562))
    ax.text(.04,.426,"INDEPENDENT CHECKING AND NEGOTIATION",ha="left",va="center",
            weight="semibold",fontsize=8.6,color=ACCENT)
    ax.plot([.04,.96],[.448,.448],color="#cad4de",lw=.9,linestyle=(0,(4,3)))
    box(ax,.04,.177,.27,.164,"Independent referee","Rebuild the coverage\nCheck exact stopping boundary",face="#eff5f1",edge=ACCENT)
    box(ax,.365,.177,.27,.164,"Public ranked prefix","Public score and semantic key\nExact full prefix or short domain",face="#eff5f1",edge=ACCENT)
    box(ax,.69,.177,.27,.164,"Bilateral protocol","B2 and on-demand structure\nV1–V5 checks and acceptance",face="#eff5f1",edge=ACCENT)
    arrow(ax,(.825,.475),(.585,.348))
    arrow(ax,(.36,.26),(.315,.26),dashed=True)
    arrow(ax,(.64,.26),(.685,.26))
    box(ax,.69,.015,.27,.095,"Private preferences","Application and network",face="#f9f5ec",edge="#8b744e")
    arrow(ax,(.825,.115),(.825,.171))
    TARGET.mkdir(exist_ok=True)
    for extension in ("png","pdf"):
        fig.savefig(TARGET/f"fig01_csods_workflow.{extension}",dpi=300)
    plt.close(fig)


if __name__=="__main__":
    main()
