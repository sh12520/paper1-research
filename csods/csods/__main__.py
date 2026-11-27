"""Command-line demonstration over the bundled two-profile fixture."""

import argparse
import json

from .depth_search import DepthCursor
from .example import public_example
from .generic_search import GenericCursor
from .grammar_search import Limits, SearchLimit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=("csods", "generic"), default="csods")
    parser.add_argument("--depth", choices=(1, 2, 3), type=int, default=2)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--conditional", action="store_true", help="Add a typed If production.")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    constructor = DepthCursor if args.method == "csods" else GenericCursor
    cursor = constructor(
        public_example(conditional=args.conditional), args.depth,
        Limits(wall_seconds=15, expanded=50000, frontier=50000),
    )
    rows = []
    status = "prefix"
    try:
        for _ in range(args.top_k):
            entry = cursor.next_contract()
            if entry is None:
                status = "exhausted"
                break
            rows.append({
                "semantic_key": entry.key.hex(), "public_score": entry.score,
                "witness": json.loads(entry.witness),
            })
    except SearchLimit as exc:
        status = str(exc)
    print(json.dumps({
        "method": args.method, "depth": args.depth, "status": status,
        "emitted": rows, "search_metrics": cursor.metrics(),
    }, indent=2))


if __name__ == "__main__":
    main()
