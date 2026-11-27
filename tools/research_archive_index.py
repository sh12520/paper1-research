"""Check or regenerate the compact directory view of the archive manifest."""

import argparse
import csv
import io
from collections import Counter
from pathlib import Path


ARCHIVE = Path(__file__).resolve().parents[1] / "archive"
MANIFEST = ARCHIVE / "MANIFEST.tsv"
DIRECTORY_INDEX = ARCHIVE / "DIRECTORY_INDEX.tsv"


def directory_bucket(relative_path):
    """Partition paths into direct-file buckets and disjoint recursive subtrees."""
    parts = relative_path.split("/")
    if any(part in ("", ".", "..") for part in parts) or "\\" in relative_path:
        raise ValueError(f"Invalid manifest path {relative_path!r}")
    directories = parts[:-1]
    cutoff = 3 if directories[:2] == ["genspace", "results"] else 2
    directory = "/".join(directories[:cutoff]) or "."
    return directory, "direct" if len(directories) < cutoff else "recursive"


def generate_index():
    """Read only manifest metadata and return the TSV bytes and aggregate totals."""
    counts = Counter()
    sizes = Counter()
    seen = set()
    with MANIFEST.open(encoding="utf-8", newline="") as manifest:
        rows = csv.reader(manifest, delimiter="\t")
        if next(rows, None) != ["relative_path", "bytes", "sha256"]:
            raise ValueError("Unexpected MANIFEST.tsv columns")
        for relative_path, size_text, _ in rows:
            if relative_path in seen:
                raise ValueError(f"Duplicate manifest path {relative_path!r}")
            bucket = directory_bucket(relative_path)
            size = int(size_text)
            if size < 0:
                raise ValueError(f"Negative file size for {relative_path!r}")
            counts[bucket] += 1
            sizes[bucket] += size
            seen.add(relative_path)

    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(["relative_directory", "scope", "files", "raw_bytes"])
    for (directory, scope), count in sorted(counts.items()):
        writer.writerow([directory, scope, count, sizes[directory, scope]])
    return output.getvalue().encode("utf-8"), len(counts), len(seen), sum(sizes.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate archive/DIRECTORY_INDEX.tsv (default: check for index drift).",
    )
    args = parser.parse_args()
    try:
        content, directory_count, files, raw_bytes = generate_index()
        if args.write:
            DIRECTORY_INDEX.write_bytes(content)
        elif not DIRECTORY_INDEX.is_file() or DIRECTORY_INDEX.read_bytes() != content:
            parser.exit(1, "Directory index differs from MANIFEST.tsv. Run with --write.\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{directory_count} directory buckets, {files:,} files, {raw_bytes:,} raw bytes")


if __name__ == "__main__":
    main()
