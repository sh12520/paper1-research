"""Checkpointed delivery runner. The only automatic jobs are manuscript jobs."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import file_digest
import json
import msvcrt
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import monotonic, sleep

DELIVERY = Path(__file__).resolve().parents[1]
ROOT = DELIVERY.parent
WORK = DELIVERY / "work"
STATE = DELIVERY / "AUTO_72H_STATE.json"
PROGRESS = DELIVERY / "AUTO_72H_PROGRESS.md"
NEXT = DELIVERY / "AUTO_72H_NEXT_ACTIONS.md"
JOURNAL = DELIVERY / "AUTO_72H_EXECUTION_LOG.md"
LOCK = WORK / "state.lock"
TZ = timezone(timedelta(hours=8))
TITLE = "AUTO_PAPER_72H"
STAGES = (
    "startup_audit", "outline", "methods", "literature", "evidence", "initial_draft",
    "review_round_1", "revision_1", "review_round_2", "revision_2",
    "review_round_3", "revision_3", "whole_manuscript_review",
    "final_text", "export", "quality", "handoff",
)
REQUIRES = {"export": ("final_text",), "quality": ("export",)}
AUTOMATIC = {"export": ("build_manuscript.py", 420), "quality": ("verify_delivery.py", 120)}


def now():
    return datetime.now(TZ)


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def atomic(path, data):
    scratch = path.with_name(f".{path.name}.{os.getpid()}.pending")
    with scratch.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(scratch, path)


@contextmanager
def guard():
    WORK.mkdir(exist_ok=True)
    with LOCK.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if not stream.tell():
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def current():
    return json.loads(STATE.read_bytes())


def journal(note):
    if not JOURNAL.exists():
        JOURNAL.write_text("# AUTO_PAPER_72H 执行日志\n\n", encoding="utf-8")
    with JOURNAL.open("a", encoding="utf-8") as stream:
        stream.write(f"- {now().isoformat(timespec='seconds')}  {note}\n")


def artifact_map(items):
    result = {}
    for item in items:
        path = (DELIVERY / item).resolve(strict=True)
        if not path.is_relative_to(DELIVERY) or not path.is_file():
            raise ValueError("Checkpoint artifacts must be delivery files")
        result[path.relative_to(DELIVERY).as_posix()] = sha(path)
    return result


def sound(record):
    if record["status"] != "COMPLETE":
        return False
    return all((DELIVERY / item).is_file() and sha(DELIVERY / item) == hash_
               for item, hash_ in record["files_sha256"].items())


def save(state):
    atomic(STATE, json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    status = [f"- {name} · {row['status']}" for name, row in state["tasks"].items()]
    atomic(PROGRESS, f"# {TITLE} 当前进度\n\n截止时间 {state['deadline_asia_shanghai']}。\n\n" +
           "\n".join(status) + "\n")
    pending = [name for name, row in state["tasks"].items() if row["status"] != "COMPLETE"]
    atomic(NEXT, "# AUTO_PAPER_72H 恢复顺序\n\n" +
           ("\n".join(f"- {name}" for name in pending) if pending else "全部交付任务已检查点。") +
           "\n\n精确恢复命令在 PAPER1_REPRODUCIBILITY.md。以签署和 release receipt 核验正式实验。\n")


def init():
    with guard():
        if STATE.exists():
            return current()
        started = now()
        pin_files = ("METHOD_FINAL_FREEZE_MANIFEST.json", "METHOD_EXECUTION_SNAPSHOT_DRAFT.json",
                     "results/depth3_proof/METHOD_DEPTH3_PROOF_EXECUTION_ADDENDUM_DRAFT.json")
        state = {
            "workflow": TITLE,
            "started_asia_shanghai": started.isoformat(),
            "deadline_asia_shanghai": (started+timedelta(hours=72)).isoformat(),
            "last_activity": started.isoformat(),
            "research_snapshot_sha256_by_file": {p:sha(ROOT / p) for p in pin_files},
            "tasks": {name:{"status":"PENDING", "files_sha256":{}} for name in STAGES},
            "running": None, "watchdog": None, "continuation_calls": 0,
            "latest_checkpoint": None, "failure_reason": None,
            "paths": {"manuscript": str(DELIVERY / "PAPER1_FINAL_FOR_HUMAN_REVIEW.md"),
                      "figures": str(DELIVERY / "PAPER1_FIGURES"), "tables": str(DELIVERY / "PAPER1_TABLES"),
                      "authorized_result_root_if_released": str(ROOT / "results/method_confirmation")},
            "resume": f'& "{sys.executable}" -B "{Path(__file__).resolve()}" resume',
        }
        save(state)
        journal("初始化有限时编排器与基线摘要。")
        return state


def verify_pins(state):
    if any(not (ROOT / p).is_file() or sha(ROOT / p) != digest
           for p,digest in state["research_snapshot_sha256_by_file"].items()):
        raise RuntimeError("Research snapshot drift. Preserve the checkpoint and review the new bytes.")


def update_state(action):
    with guard():
        state = current()
        action(state)
        save(state)
        return state


def checkpoint(stage, files, note):
    def record(state):
        verify_pins(state)
        state["tasks"][stage] = {"status":"COMPLETE", "files_sha256":artifact_map(files),
                                 "updated":now().isoformat(), "note":note}
        state["latest_checkpoint"] = stage
        state["last_activity"] = now().isoformat()
        journal(stage+" 完成。"+note)
    update_state(record)


def changed(state):
    for name, record in state["tasks"].items():
        if record["status"] == "COMPLETE" and not sound(record):
            record["status"] = "STALE"
            journal(name+" 工件摘要漂移，保留先前记录。")


def identity(pid):
    sys.path.insert(0, str(ROOT))
    from src.process_lifecycle import identity as get_identity
    return get_identity(pid)


def active(record):
    return record and record.get("identity") and identity(record["pid"]) == record["identity"]


def launch_job(command, limit, stage):
    sys.path.insert(0, str(ROOT))
    from src.windows_suspended_job import launch
    owner = os.getpid()

    def reserve(state):
        if active(state["running"]):
            raise RuntimeError("A supervised task is already running")
        verify_pins(state)
        state["running"] = {"pid":owner, "identity":identity(owner), "stage":stage}
    update_state(reserve)
    log = WORK / f"{stage}-{now():%Y%m%d-%H%M%S}.log"
    job = None
    try:
        job = launch(command, cwd=DELIVERY, stdout_path=log)
        def describe(state):
            state["running"].update(child_pid=job.pid, child_identity=job.identity, log=log.name)
        update_state(describe)
        end = monotonic() + limit
        while job.poll() is None:
            if monotonic() >= end:
                job.terminate()
                job.wait(5)
                raise TimeoutError(f"{stage} exceeded its bounded worker time")
            sleep(.18)
        code = job.poll()
        result = job.finish(expected_exit=code)
        if code or not result["pass"]:
            raise RuntimeError(f"{stage} failed, exit={code}, see {log.name}")
        return log
    finally:
        if job is not None:
            job.close()
        def release(state):
            if state["running"] and state["running"]["pid"] == owner:
                state["running"] = None
        update_state(release)


def fail(stage, error):
    def record(state):
        state["failure_reason"] = {"stage":stage,"reason":str(error),"timestamp":now().isoformat()}
        if stage in state["tasks"] and state["tasks"][stage]["status"] != "COMPLETE":
            state["tasks"][stage]["status"] = "FAILED"
        journal(f"{stage} 记录失败。{error}")
    update_state(record)


def resume():
    with guard():
        state = current()
        verify_pins(state)
        changed(state)
        if state["running"] and not active(state["running"]):
            journal("发现已退出的监督进程，继续从有效工件检查点恢复。")
            state["running"] = None
        save(state)
    deadline = datetime.fromisoformat(state["deadline_asia_shanghai"])
    for stage,(script, cap) in AUTOMATIC.items():
        state = current()
        if sound(state["tasks"][stage]) or not all(sound(state["tasks"][p]) for p in REQUIRES[stage]):
            continue
        if (DELIVERY / "automation" / script).is_file() and now() < deadline:
            try:
                launch_job([sys.executable,"-B",str(DELIVERY / "automation" / script)],
                           min(cap, (deadline-now()).total_seconds()), stage)
                files = (["PAPER1_FINAL_FOR_HUMAN_REVIEW.md", "PAPER1_FINAL_FOR_HUMAN_REVIEW.docx",
                          "PAPER1_FINAL_FOR_HUMAN_REVIEW.pdf"]
                         if stage=="export" else ["work/mechanical_qa.json"])
                checkpoint(stage, files, "Windows Job 子进程已结束及复核。")
            except Exception as error:
                fail(stage, error)
                raise
    return current()


def watch():
    owner = os.getpid()
    def attach(state):
        if active(state["watchdog"]):
            raise RuntimeError("A watchdog is already active")
        state["watchdog"] = {"pid":owner,"identity":identity(owner)}
        journal("Windows 本地续作进程启动。")
    update_state(attach)
    try:
        while True:
            state = current()
            verify_pins(state)
            deadline = datetime.fromisoformat(state["deadline_asia_shanghai"])
            if now() >= deadline or sound(state["tasks"]["handoff"]):
                break
            stale_s = (now() - datetime.fromisoformat(state["last_activity"])).total_seconds()
            if state["running"] and active(state["running"]):
                sleep(15)
                continue
            if stale_s >= 20 * 60:
                if any(sound(state["tasks"][deps[0]]) and state["tasks"][stage]["status"] in {"PENDING","STALE"}
                       for stage,deps in REQUIRES.items()):
                    try:
                        resume()
                    except (RuntimeError,OSError):
                        pass
                elif state["continuation_calls"] < 3 and (WORK/"cli_probe_pass.json").is_file():
                    def count(s):
                        s["continuation_calls"] += 1
                        s["last_activity"] = now().isoformat()
                        journal("检测到作者检查点停滞，调用已探测的 Codex CLI 继续完成论文。")
                    update_state(count)
                    cli = shutil.which("codex")
                    if not cli:
                        raise RuntimeError("Codex executable disappeared")
                    try:
                        launch_job([cli,"exec","--skip-git-repo-check","--sandbox","workspace-write",
                                    "--cd",str(DELIVERY),"--color","never",
                                    (WORK/"continuation_prompt.md").read_text(encoding="utf-8")],
                                   min(60*60,(deadline-now()).total_seconds()),"authoring_continuation")
                    except Exception as error:
                        fail("authoring_continuation",error)
            sleep(15)
    finally:
        def detach(state):
            state["watchdog"] = None
            journal("Windows 本地续作进程退出。")
        update_state(detach)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    for mode in ("init","status","resume","watch","heartbeat"):
        modes.add_parser(mode)
    mark = modes.add_parser("checkpoint")
    mark.add_argument("stage", choices=STAGES)
    mark.add_argument("files", nargs="+")
    mark.add_argument("--note",default="")
    args = parser.parse_args()
    if args.mode=="init":
        init()
    elif args.mode=="checkpoint":
        checkpoint(args.stage,args.files,args.note)
    elif args.mode=="resume":
        resume()
    elif args.mode=="watch":
        watch()
    elif args.mode=="heartbeat":
        update_state(lambda state:state.update(last_activity=now().isoformat()))
    else:
        s = current()
        print(json.dumps({k:s[k] for k in ("deadline_asia_shanghai","running","watchdog",
                                          "latest_checkpoint","failure_reason")}, ensure_ascii=False))


if __name__=="__main__":
    main()
