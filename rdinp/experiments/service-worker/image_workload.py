"""Fixed image workload shared by the sequential and concurrent RDINP studies."""

import io

from PIL import Image, ImageFilter


def detect_edges(payload: bytes, side: int) -> bytes:
    with Image.open(io.BytesIO(payload)) as image:
        gray = image.convert("L").resize((side, side), Image.Resampling.BILINEAR)
    edge_map = gray.filter(ImageFilter.GaussianBlur(radius=1)).filter(ImageFilter.FIND_EDGES)
    result = io.BytesIO()
    edge_map.save(result, format="PNG", compress_level=1)
    return result.getvalue()


def compute_edge(payload: bytes) -> bytes:
    return detect_edges(payload, 512)


def compute_local(payload: bytes) -> bytes:
    return detect_edges(payload, 256)
