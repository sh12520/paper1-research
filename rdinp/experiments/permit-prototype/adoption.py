"""Terminal fallback shared by the paired run and acceptance fixtures."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service-worker"))
from image_workload import compute_local


def wait_until(target_ns):
    delay_ns = target_ns - time.perf_counter_ns()
    while delay_ns > 0:
        time.sleep(delay_ns / 1e9)
        delay_ns = target_ns - time.perf_counter_ns()


def fallback(source: bytes, deadline_ns: int, fallback_ns: int):
    """Execute the local image path, then sample the terminal adoption boundary."""
    wait_until(fallback_ns)
    data = compute_local(source)
    done_ns = time.perf_counter_ns()
    return data, done_ns, done_ns < deadline_ns
