"""Exact external-sort audit infrastructure; never runs research fixtures.

Records are losslessly serialized full public semantic signatures; SHA digests
are used only for integrity, never as equality keys. The input stream supplied
by the caller must be an independently constructed syntax stream. Temporary
runs are scoped to a newly created directory and removed after successful use.
"""
from __future__ import annotations
import gzip
import heapq
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from itertools import islice


def encode_signature(signature):
    """JSON encodes tuple-based semantic keys losslessly for this schema.

    All keys have fixed structural positions; JSON arrays reconstruct as
    tuples. Numeric profile positions use configured finite non-NaN floats.
    The encoding is not a cryptographic hash.
    """
    return json.dumps(signature, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('ascii') + b'\n'


def _write_gzip(path, values):
    with gzip.open(path, 'wb') as out:
        for value in values:
            out.write(value)


def _iter_gzip(path):
    with gzip.open(path, 'rb') as stream:
        yield from stream


def _unique_sorted(iterable):
    previous = None
    for value in iterable:
        if value != previous:
            yield value
            previous = value


def external_unique(records, destination, *, workspace=None, chunk_size=10000, merge_width=32):
    """Sort, exactly deduplicate and gzip records, bounded by chunk size.

    `records` yields full newline-terminated byte keys, not hashed values.
    Refuse overwrite. Returns the number of input and unique records. A
    chunk-size bound is not a byte-memory bound for arbitrarily long records.
    The algorithm never intentionally truncates its input.
    """
    destination = Path(destination)
    if destination.exists(): raise FileExistsError(destination)
    if chunk_size < 1 or merge_width < 2: raise ValueError('bad sort parameters')
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with TemporaryDirectory(prefix='semantic_ref_', dir=workspace) as temp:
        temp = Path(temp)
        runs=[]
        iterator=iter(records)
        while True:
            chunk=list(islice(iterator, chunk_size))
            if not chunk: break
            if any(not isinstance(v,bytes) or not v.endswith(b'\n') or b'\n' in v[:-1] for v in chunk):
                raise ValueError('expected single-line byte keys')
            count += len(chunk)
            run=temp / f'chunk-{len(runs):08}.gz'
            _write_gzip(run, sorted(set(chunk)))
            runs.append(run)
        generation=0
        while len(runs) > 1:
            new=[]
            for i in range(0, len(runs), merge_width):
                group=runs[i:i+merge_width]
                target=temp / f'merge-{generation:03}-{i//merge_width:08}.gz'
                _write_gzip(target, _unique_sorted(heapq.merge(*(_iter_gzip(p) for p in group))))
                new.append(target)
                for path in group: path.unlink()
            runs=new
            generation+=1
        unique=0
        def output():
            nonlocal unique
            if runs:
                for value in _iter_gzip(runs[0]):
                    unique += 1
                    yield value
        _write_gzip(destination, output())
    return {'input_count':count, 'unique_count':unique, 'output_bytes':destination.stat().st_size}


def compare_sorted(left, right):
    """Exact streaming comparison of two sorted gzip outputs; no hashes."""
    a, b = _iter_gzip(left), _iter_gzip(right)
    sentinel=object()
    from itertools import zip_longest
    for x, y in zip_longest(a, b, fillvalue=sentinel):
        if x != y: return False
    return True
