"""Check supplement integrity and recalculate the published timing summary."""

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median, quantiles


ROOT = Path(__file__).resolve().parent


def main():
    checks = (ROOT / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    actual = {item.relative_to(ROOT).as_posix() for item in ROOT.rglob("*")
              if item.is_file() and item.name != "SHA256SUMS.txt"}
    for line in checks:
        expected, name = line.split("  ", 1)
        if name not in actual or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Package checksum mismatch: {name}")
        actual.remove(name)
    if actual:
        raise ValueError(f"Supplement manifest omits {sorted(actual)}")

    with (ROOT / "S9_depth3_audited_stage_times.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 24 or len({row["instance_id"] for row in rows}) != 24:
        raise ValueError("Missing or duplicate timing query")
    pieces = ("native_checkpoint_s", "emission_s", "independent_check_s")
    for row in rows:
        seconds = math.fsum(float(row[key]) for key in pieces)
        if seconds != float(row["audited_stage_sum_s"]):
            raise ValueError("Stage total differs from three recorded clocks")
    values = [float(row["audited_stage_sum_s"]) for row in rows]
    derived = {"median": median(values), "p95": quantiles(values, n=100, method="inclusive")[94],
               "max": max(values), "sum": math.fsum(values)}
    expected = json.loads((ROOT / "S9_depth3_audited_stage_summary.json").read_bytes())
    if derived != expected["all"]["seconds"]["audited_stage_sum_s"]:
        raise ValueError("Summary differs from reanalysis of per-query costs")
    print(f"{len(checks)} supplement files verified. 24 paired stage totals. "
          f"Median {derived['median']:.3f} s, p95 {derived['p95']:.3f} s.")


if __name__ == "__main__":
    main()
