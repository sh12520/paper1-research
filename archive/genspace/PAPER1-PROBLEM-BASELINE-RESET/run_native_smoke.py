"""Check two frozen ns-3 entry points without rewriting historical runs."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


ARTIFACT = Path("D:/msys2/home/16043/research/TFH02-SUBMISSION-CAMPAIGN-20261110-003718")
RUNS = Path(__file__).resolve().parent / "native_replay"
EXE = ARTIFACT / "artifacts/contrib/nr/examples/ns3.42-cttc-nr-fh-xr.exe"
LIB = ARTIFACT / "artifacts/lib"
MODELS = ("OptimizeMcs", "OptimizeRBs")
PORTS = {1121: "AR_Pose", 1122: "AR_Video", 1123: "AR_Audio", 1131: "VR", 1141: "CG", 1254: "VoIP"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
        (name, ctypes.c_uint64) for name in (
            "total_phys", "available", "total_page", "available_page", "total_virtual",
            "available_virtual", "extended_virtual",
        )
    ]


def available():
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("Cannot read physical memory")
    return status.available


def run(mode):
    baseline = ARTIFACT / "runs" / f"{mode}-R7-T1" / "metadata.json"
    original = json.loads(baseline.read_bytes())
    if original["status"] != "PASS" or original["executable_sha256"] != sha(EXE):
        raise ValueError("Unexpected historical reference or executable digest")
    if sha(LIB / "libns3.42-flow-monitor.dll") != original["flow_monitor_sha256"]:
        raise ValueError("FlowMonitor DLL changed")
    nr = json.loads((ARTIFACT / "evidence/build-summary.json").read_bytes())["nr_sha256"]
    if sha(LIB / "libns3.42-nr.dll") != nr:
        raise ValueError("NR DLL changed")
    if available() < 768 * 2**20:
        raise RuntimeError("Below the historical 768 MiB launch floor")
    argv = [str(EXE), *original["argv"][1:]]
    if argv.count("--appDuration=5000") != 1 or "--tfhProfile=transient" not in argv:
        raise ValueError("Unexpected application duration argument")
    target = RUNS / mode
    target.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    if env.get("NS_GLOBAL_VALUE") or env.get("NS_ATTRIBUTE_DEFAULT"):
        raise ValueError("Unexpected simulator environment override")
    env["PATH"] = original["PATH"]
    minimum_available = available()
    started = time.monotonic()
    with (target / "stdout.log").open("wb") as out, (target / "stderr.log").open("wb") as err:
        with subprocess.Popen(argv, cwd=target, env=env, stdout=out, stderr=err) as proc:
            while proc.poll() is None:
                minimum_available = min(minimum_available, available())
                if time.monotonic() - started > 1200 or minimum_available < 512 * 2**20:
                    proc.kill()
                    break
                time.sleep(0.5)
            code = proc.wait()
    output = {"mode": mode, "argv": argv, "exit_code": code, "wall_s": time.monotonic() - started,
              "minimum_available_bytes": minimum_available, "exe_sha256": sha(EXE), "nr_dll_sha256": nr,
              "reference_metadata_sha256": sha(baseline)}
    if code == 0:
        import re

        flows = {}
        for match in re.finditer(r"^Flow\s+(\d+)\s+\(([^:]+):(\d+) -> ([^:]+):(\d+)\) proto (\w+)\s*$",
                                 (target / "stdout.log").read_text(encoding="utf-8"), re.M):
            if match[6] == "UDP" and int(match[5]) in PORTS:
                flows[match[1]] = (match[2], match[3], match[4], match[5])
        events = {}
        with (target / "packet-events.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                flow = flows.get(row["flow_id"])
                if flow is None:
                    continue
                key = (flow, row["packet_id"])
                seen = events.setdefault(key, {})
                event = row["event"].upper()
                if event in seen:
                    raise ValueError(f"Duplicate {event}")
                seen[event] = (int(row["time_ns"]), int(row["ip_bytes"]))
        stats = Counter()
        source_tx = []
        for (flow, packet), event in events.items():
            assert "TX" in event
            tx, size = event["TX"]
            if not 400_000_000 <= tx < 5_400_000_000:
                continue
            source_tx.append((flow, packet, tx, size))
            app = PORTS[int(flow[3])]
            windows = ["all"]
            if 2_400_000_000 <= tx < 3_400_000_000:
                windows.append("LOW")
            elif 3_400_000_000 <= tx < 4_400_000_000:
                windows.append("RECOVERY1")
            for window in windows:
                stats[(window, app, "tx")] += 1
            if "RX" in event:
                rx, received_size = event["RX"]
                assert received_size == size and rx >= tx
                status = "within_10ms" if rx - tx <= 10_000_000 else "late"
            else:
                status = "not_observed"
            for window in windows:
                stats[(window, app, status)] += 1
        if not source_tx or len(flows) != 18:
            raise ValueError("Incomplete smoke traffic")
        output["traffic"] = {
            window: {app: {k: stats[(window, app, k)] for k in ("tx", "within_10ms", "late", "not_observed")}
                     for app in PORTS.values()}
            for window in ("all", "LOW", "RECOVERY1")
        }
        output["source_tx_sha256"] = hashlib.sha256(json.dumps(sorted(source_tx)).encode()).hexdigest()
        output["capacity_sha256"] = sha(target / "capacity-events.csv")
        output["topology_sha256"] = sha(target / "uePositions.txt")
        output["raw_archive_byte_matches"] = {
            name: sha(target / name) == sha(baseline.parent / "output" / name)
            for name in ("uePositions.txt", "capacity-events.csv", "packet-events.csv")
        }
    (target / "receipt.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output), flush=True)
    return output


if __name__ == "__main__":
    workers = 2 if available() >= 1536 * 2**20 else 1
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(run, MODELS))
    valid = all(row["exit_code"] == 0 for row in results)
    paired_fields = ("source_tx_sha256", "capacity_sha256", "topology_sha256")
    pairing = {key: valid and results[0][key] == results[1][key] for key in paired_fields}
    print(json.dumps({"workers": workers, "paired": pairing, "all_completed": valid}), flush=True)
    if not all(pairing.values()):
        raise SystemExit(1)
