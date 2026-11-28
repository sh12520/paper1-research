"""Freeze the delivered RDINP source and evidence into a verified ZIP.

Build from the repository root with --out NEW.zip and optional --paper DIR.
Use --verify EXISTING.zip to check the manifest of a delivered archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

EXPERIMENT = Path(__file__).resolve().parent
ROOT = EXPERIMENT.parents[2]
RDINP = ROOT / "rdinp"
STEP1 = RDINP / "experiments" / "structured-fast-slow"
STEP1_RUN = STEP1 / "runs" / "step1-20261128-r02"
STEP1_FROZEN = STEP1 / "evidence" / "step1-20261128-r02"
ATTRIBUTION = STEP1 / "evidence" / "step1-attribution-20261128-r02"
EVIDENCE = EXPERIMENT / "evidence" / "step2-20261128-r01"
C2 = RDINP / "protocol" / "c2"
TRACE = ROOT / "archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/native_replay/OptimizeRBs/capacity-events.csv"
STAMP = (1980, 1, 1, 0, 0, 0)
MANIFEST = "SHA256SUMS.txt"
README = "REPRODUCIBILITY.md"
PAPER_STEM = "RDINP_中文小论文初稿"
ARM_FILE = r"(?:authority-audit\.json|tasks\.json|rpc\.jsonl\.gz|wire\.jsonl\.gz)"
ARM_PATH = re.compile(
    r"pairs/(?:headroom-(?:main|light)|pair-(?:plain|half|dynamic)-[0-9]+/"
    r"(?:Structured-RDINP|Reactive-ReNeg))/" + ARM_FILE
)
BENCHMARK_FILES = {
    ".gitattributes", "RESULTS.md", "gate.json", "c2/c2_cost.json", "safety/safety.json",
    "pairs/COMPLETE.json", "pairs/plan.json", "pairs/headroom.json", "pairs/per_task.csv", "pairs/per_arm.csv",
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_file(path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean_name(name):
    if not name or "\\" in name or ":" in name or any(part in ("", ".", "..") for part in name.split("/")):
        raise ValueError(f"Invalid relative member name: {name!r}")
    return name


def parse_manifest(text):
    entries = {}
    for line in text.splitlines():
        checksum, _, name = line.partition("  ")
        clean_name(name)
        if not re.fullmatch(r"[a-f0-9]{64}", checksum) or name in entries:
            raise ValueError(f"Invalid or duplicate manifest entry: {name}")
        entries[name] = checksum
    if not entries:
        raise ValueError("Checksum manifest is empty")
    return entries


def match_file(path, expected):
    if sha(path) != expected:
        raise ValueError(f"Checksum mismatch: {path}")


def match_result(root, complete):
    for name, expected in complete["sha256"].items():
        match_file(root / clean_name(name), expected)


def files_for_paper(paper):
    if paper.is_dir():
        markdown = paper / (PAPER_STEM + ".md")
    elif paper.suffix.lower() == ".md":
        markdown = paper
    else:
        raise ValueError("--paper must be the delivery directory or its Markdown draft")
    directory = markdown.parent
    figures = directory / "figures"
    images = sorted(figures.glob("*.png"))
    vectors = sorted(figures.glob("*.pdf"))
    if not images or len(images) != len(vectors) or {x.stem for x in images} != {x.stem for x in vectors}:
        raise ValueError("Paper figures must have matching PNG and PDF pairs")
    notes = [
        path for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in {".md", ".bib", ".py", ".ps1", ".sh"}
        and re.search(r"reference|citation|figure|readme|render|draft|引文|文献", path.stem, re.IGNORECASE)
    ]
    return [markdown, markdown.with_suffix(".docx"), *notes, *images, *vectors]


def collect_files(paper):
    files = [
        EXPERIMENT / name for name in (
            "README.md", "adoption.py", "check_protocol.py", "measure_c2.py", "run_pairs.py",
            "gate.py", "reproduce.py", "freeze_bundle.py", "plot_paper.py",
        )
    ]
    for name in ("requirements-figures.txt", "render_paper.py", "render_paper.ps1", "C2_COST.md"):
        path = EXPERIMENT / name
        if path.is_file():
            files.append(path)

    files += [
        RDINP / "requirements.txt", RDINP / "experiments/service-worker/image_workload.py", TRACE,
    ]
    files += [C2 / clean_name(name) for name in json_file(C2 / "SOURCE-FILES.json")["files"]]
    files += [
        RDINP / "protocol/permit-v1" / name
        for name in ("README.md", "permit.py", "permit.schema.json", "permit_server.py", "permit_wire.py")
    ]
    files += [
        STEP1 / name for name in (
            "README.md", "run.py", "analysis.py", "audit.py", "sim.py", "run_attribution.py", "calibrate.py",
            "calibration.json", "STEP1_REPORT.md", "STEP1_REVIEW.md", "STEP1_CONTROL_BUDGET.md",
            "evidence/step1-c2-control-budget.json",
        )
    ]

    step1 = json_file(STEP1_RUN / "COMPLETE.json")
    match_result(STEP1_RUN, step1)
    match_file(TRACE, json_file(STEP1_RUN / "plan.json")["trace_sha256"])
    files += [STEP1_RUN / name for name in ("per_run.csv", "per_task.csv.gz", "plan.json", "COMPLETE.json", "AUDIT.json")]
    files += [STEP1_FROZEN / name for name in ("COMPLETE.json", "plan.json", "AUDIT.json")]
    files.extend(
        path for path in sorted((STEP1_FROZEN / "analysis").iterdir())
        if path.is_file() and path.suffix in {".csv", ".md", ".pdf", ".png"}
    )
    attribution = json_file(ATTRIBUTION / "COMPLETE.json")
    match_result(ATTRIBUTION, attribution)
    files.extend(ATTRIBUTION / name for name in attribution["sha256"])
    files.extend(ATTRIBUTION / name for name in ("COMPLETE.json", "fast-switch-effect.png"))

    evidence_manifest = EVIDENCE / MANIFEST
    evidence = parse_manifest(evidence_manifest.read_text(encoding="utf-8"))
    if not BENCHMARK_FILES <= set(evidence):
        raise ValueError("Step 2 evidence is missing required manifest entries")
    for name, expected in evidence.items():
        if name not in BENCHMARK_FILES and not ARM_PATH.fullmatch(name):
            raise ValueError(f"Step 2 evidence member is outside the export allowlist: {name}")
        path = EVIDENCE / name
        match_file(path, expected)
        files.append(path)
    files.append(evidence_manifest)
    match_result(EVIDENCE / "pairs", json_file(EVIDENCE / "pairs" / "COMPLETE.json"))
    for name, expected in json_file(EVIDENCE / "pairs" / "plan.json")["source_sha256"].items():
        path = RDINP / clean_name(name)
        match_file(path, expected)
        files.append(path)
    if paper is not None:
        files.extend(files_for_paper(paper))

    paths = {}
    for path in files:
        resolved = path.resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(ROOT):
            raise ValueError(f"Expected a regular file inside the repository: {path}")
        if resolved != path.absolute():
            raise ValueError(f"Refusing a symbolic link in the export: {path}")
        label = clean_name(path.relative_to(ROOT).as_posix())
        if label in (README, MANIFEST) or path.suffix in {".zip", ".sqlite", ".sqlite3", ".db", ".key", ".pem"}:
            raise ValueError(f"Artifact is not allowed in the archive: {label}")
        paths[label] = path
    return paths


def readme(paper):
    lines = [
        "# RDINP GOAL-1 冻结复现包",
        "",
        "从解压后的仓库根目录运行。包内的 Step 1 r02 是封存仿真数据，Step 2 是同主机真实环回协议实测，链路扰动由实验程序注入。",
        "原始任务记录、聚合表、计划和协议源码保留各自的路径。试验私钥、进程配置和运行数据库在实测时生成。",
        "",
        "## 核验与复算",
        "",
        "用 Python 3.11 或更新版本执行下列命令。第一条逐项对照压缩包中的 SHA-256。第二条只对封存数据复算门禁。"
        "第三条执行一轮新的本机实测并沿用封存的 Step 1。新目录和新结果文件需选用未占用路径。",
        "",
        "~~~bash",
        "python -B rdinp/experiments/permit-prototype/freeze_bundle.py --verify <复现包.zip>",
        "python -B rdinp/experiments/permit-prototype/gate.py "
        "--pairs rdinp/experiments/permit-prototype/evidence/step2-20261128-r01/pairs "
        "--matrix rdinp/experiments/permit-prototype/evidence/step2-20261128-r01/safety/safety.json "
        "--c2 rdinp/experiments/permit-prototype/evidence/step2-20261128-r01/c2/c2_cost.json --out <新结果.json>",
        "python -B rdinp/experiments/permit-prototype/reproduce.py --assets <原图目录> --out <新目录>",
        "~~~",
        "",
        "新一轮实测自动用 rdinp/requirements.txt 创建隔离环境，需要可用的 Python 包源。也可传 --python 指定已装有锁定依赖的解释器。"
        "原图目录提供 astronaut.png、camera.png 和 coffee.png 三个 scikit-image 样图。"
        "文件摘要固定在 [标定数据](rdinp/experiments/structured-fast-slow/calibration.json)，传入的文件会逐个核验。"
        "实测时间随机器负载和平台变化，独立复算可以核验本报告的具体数字。",
        "",
        "## 重新出图",
        "",
        "绘图用 Matplotlib 3.10.3，并需要 Microsoft YaHei、Noto Sans SC、Noto Sans CJK SC 或 SimHei 中的一种字体。",
        "",
        "~~~bash",
        "python -m pip install matplotlib==3.10.3",
        "python -B rdinp/experiments/permit-prototype/plot_paper.py "
        "--pairs rdinp/experiments/permit-prototype/evidence/step2-20261128-r01/pairs "
        "--c2 rdinp/experiments/permit-prototype/evidence/step2-20261128-r01/c2/c2_cost.json "
        "--out <图表目录>",
        "~~~",
        "",
        "生成的图表同时提供 600 DPI PNG 和矢量 PDF。Step 1 数据与归因表默认从包内的冻结目录读取。",
    ]
    if paper is not None:
        markdown = paper / (PAPER_STEM + ".md") if paper.is_dir() else paper
        relative = markdown.relative_to(ROOT).as_posix()
        directory = markdown.parent.relative_to(ROOT).as_posix()
        lines.extend([
            "", "## 中文论文", "",
            f"[Markdown 主稿]({relative}) · [Word 阅读版]({markdown.with_suffix('.docx').relative_to(ROOT).as_posix()})",
            "",
            "从包的根目录用 Pandoc 可重新导出 Word。", "",
            "~~~bash",
            f'pandoc "{relative}" --resource-path="{directory}" -o "<新稿.docx>"',
            "~~~",
        ])
    return "\n".join(lines) + "\n"


def verify(archive):
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(set(names)) != len(names) or MANIFEST not in names:
            raise ValueError("ZIP has duplicate members or is missing the checksum manifest")
        entries = parse_manifest(bundle.read(MANIFEST).decode("utf-8"))
        if set(names) != set(entries) | {MANIFEST} or MANIFEST in entries or README not in entries:
            raise ValueError("ZIP member list does not match the checksum manifest")
        for name, expected in entries.items():
            with bundle.open(name) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError(f"ZIP member checksum mismatch: {name}")
        return len(entries)


def zip_member(name):
    info = zipfile.ZipInfo(name, STAMP)
    info.compress_type = zipfile.ZIP_STORED if name.endswith((".gz", ".pdf", ".png", ".docx")) else zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def freeze(archive, paper):
    paths = collect_files(paper)
    checksums = {name: sha(path) for name, path in paths.items()}
    intro = readme(paper).encode("utf-8")
    checksums[README] = hashlib.sha256(intro).hexdigest()
    manifest = "".join(f"{checksum}  {name}\n" for name, checksum in sorted(checksums.items()))
    archive.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with archive.open("xb") as stream:
            created = True
            with zipfile.ZipFile(stream, "w") as bundle:
                for name in sorted(paths):
                    with paths[name].open("rb") as source, bundle.open(zip_member(name), "w") as destination:
                        shutil.copyfileobj(source, destination)
                bundle.writestr(zip_member(README), intro)
                bundle.writestr(zip_member(MANIFEST), manifest)
        return verify(archive)
    except (Exception, KeyboardInterrupt):
        if created:
            archive.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path, help="Build a new ZIP")
    mode.add_argument("--verify", type=Path, help="Verify an existing frozen ZIP")
    parser.add_argument("--paper", type=Path, help="Optional delivery directory or Markdown draft")
    args = parser.parse_args()
    try:
        if args.verify is not None:
            if args.paper:
                parser.error("--paper is for --out only")
            archive = args.verify.resolve(strict=True)
            count = verify(archive)
        else:
            archive = args.out.resolve()
            paper = args.paper.resolve(strict=True) if args.paper else None
            count = freeze(archive, paper)
        print(f"Verified {count} archived files: {archive}")
        print(f"{sha(archive)}  {archive.name}")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Freeze validation failed: {error}\n")


if __name__ == "__main__":
    main()
