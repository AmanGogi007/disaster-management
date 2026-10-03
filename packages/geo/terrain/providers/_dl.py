"""Shared download + cache helpers for real DEM providers.

Raw source downloads are cached separately from derived/processed products so
provenance always points at the untouched original bytes.  A synthetic DEM is
never written through this cache.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

# Package layout: <repo>/packages/geo/terrain/providers -> repo root
_PROVIDERS_DIR = Path(__file__).resolve().parent
_PACKAGES_DIR = _PROVIDERS_DIR.parent.parent.parent  # packages/geo/terrain/providers -> packages/geo
_TERRAIN_DIR = _PROVIDERS_DIR.parent
_GEO_DIR = _TERRAIN_DIR.parent
_PACKAGES = _GEO_DIR.parent
_REPO = _PACKAGES.parent

DEFAULT_CACHE_RAW = _REPO / "data" / "cache" / "raw"
DEFAULT_CACHE_DEM = _REPO / "data" / "cache" / "dem"


def _sha256_path(cache_dir: Path, url: str, ext: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{h}{ext}"


def download_cached(url: str, cache_dir: Path = DEFAULT_CACHE_RAW) -> Path:
    """Download ``url`` into the raw cache (keyed by URL hash) or reuse it.

    Returns the local path to the cached raw bytes.
    """
    ext = Path(url.split("?")[0]).suffix.lower() or ".bin"
    target = _sha256_path(cache_dir, url, ext)
    if target.exists() and target.stat().st_size > 0:
        return target
    import requests

    tmp = target.with_suffix(target.suffix + f".part{os.getpid()}")
    with requests.get(url, stream=True, timeout=int(os.environ.get("DEM_DL_TIMEOUT", "120"))) as r:
        r.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    os.replace(tmp, target)
    return target
