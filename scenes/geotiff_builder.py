"""Builds a compact, "normal-photo-like" GeoTIFF preview from raw SAR bands.

Sentinel-1 GRD products ship as single-band amplitude rasters per
polarization (commonly VV + VH for IW mode). A plain ordinary photo has
3 bands (R, G, B). To keep the two projects' outputs easy to compare and
to keep the SAR *and* the GeoAI model API consuming the "closest possible
number of factors" (bands) to a normal image, this module always emits a
**3-band, 8-bit GeoTIFF**:

    band 1 -> VV   (scaled 0-255)
    band 2 -> VH   (scaled 0-255)
    band 3 -> VV/VH ratio ("pseudo color" band that approximates how a
              3rd visual channel would separate water/urban/vegetation)

If only one polarization is available, band 3 falls back to a copy of
band 1 so the output still has 3 bands.

The module has two layers:

* Pure arithmetic (``estimate_bytes`` / ``plan_downsample``) has **no**
  external dependencies and is unit-testable anywhere numpy is available.
* ``build_rgb_like_geotiff`` does the actual raster I/O with ``rasterio``
  and is only imported/called where rasterio is installed (the server).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import numpy as np

DEFAULT_MAX_BYTES = 100 * 1024 * 1024  # hard cap requested by the project owner
BAND_COUNT = 3           # "closest possible number of factors" to a normal RGB photo
BYTES_PER_PIXEL_PER_BAND = 1  # 8-bit output keeps size small and is still a "normal image"
# DEFLATE on SAR-derived, stretched 8-bit data typically lands around 55-75%
# of raw size. We budget conservatively so the *actual* compressed file,
# not just the raw pixel buffer, stays under the cap.
ASSUMED_COMPRESSION_RATIO = 0.65
SAFETY_MARGIN = 0.90  # leave 10% headroom under the hard cap


@dataclass(frozen=True)
class DownsamplePlan:
    out_width: int
    out_height: int
    scale: float          # 1.0 == no resizing
    estimated_raw_bytes: int
    estimated_compressed_bytes: int


def estimate_bytes(width: int, height: int, band_count: int = BAND_COUNT,
                    bytes_per_pixel: int = BYTES_PER_PIXEL_PER_BAND) -> int:
    """Raw (uncompressed) pixel buffer size for a width x height x bands raster."""
    if width <= 0 or height <= 0:
        return 0
    return int(width) * int(height) * int(band_count) * int(bytes_per_pixel)


def plan_downsample(width: int, height: int, max_bytes: int = DEFAULT_MAX_BYTES,
                     band_count: int = BAND_COUNT,
                     bytes_per_pixel: int = BYTES_PER_PIXEL_PER_BAND,
                     compression_ratio: float = ASSUMED_COMPRESSION_RATIO,
                     safety_margin: float = SAFETY_MARGIN) -> DownsamplePlan:
    """Work out how much a width x height raster must shrink to respect max_bytes.

    Scales width and height by the same factor (keeps the pixel/ground
    resolution isotropic) so the GeoTIFF's geotransform stays simple to
    recompute: new_pixel_size = old_pixel_size / scale.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    budget = max_bytes * safety_margin / max(compression_ratio, 1e-6)
    raw_bytes = estimate_bytes(width, height, band_count, bytes_per_pixel)
    if raw_bytes <= budget:
        scale = 1.0
    else:
        # raw_bytes shrinks with scale**2 because both width and height shrink.
        scale = math.sqrt(budget / raw_bytes)
        scale = max(scale, 1e-6)

    out_width = max(1, int(width * scale))
    out_height = max(1, int(height * scale))
    estimated_raw = estimate_bytes(out_width, out_height, band_count, bytes_per_pixel)
    estimated_compressed = int(estimated_raw * compression_ratio)
    return DownsamplePlan(
        out_width=out_width, out_height=out_height, scale=scale,
        estimated_raw_bytes=estimated_raw, estimated_compressed_bytes=estimated_compressed,
    )


def stretch_to_uint8(band: np.ndarray, low_pct: float = 2.0, high_pct: float = 98.0) -> np.ndarray:
    """Percentile-stretch a float SAR amplitude/ratio band into 0-255 uint8.

    SAR amplitude is heavy-tailed, so a plain min/max stretch would crush
    almost everything into a few gray levels; a percentile stretch is the
    standard fix and is what keeps the output visually close to an
    ordinary 8-bit photo band.
    """
    finite = band[np.isfinite(band)]
    if finite.size == 0:
        return np.zeros(band.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, [low_pct, high_pct])
    if hi <= lo:
        hi = lo + 1e-6
    clipped = np.clip(band, lo, hi)
    clipped = np.nan_to_num(clipped, nan=lo)
    scaled = (clipped - lo) / (hi - lo) * 255.0
    return scaled.astype(np.uint8)


def build_band_stack(vv: np.ndarray, vh: np.ndarray | None = None) -> np.ndarray:
    """Return a (3, H, W) uint8 stack: VV, VH, VV/VH ratio ("pseudo-RGB").

    Falls back to duplicating VV for bands 2/3 when VH is missing, so the
    output always carries exactly BAND_COUNT bands, matching a normal photo.
    """
    vv = np.asarray(vv, dtype=np.float32)
    if vh is None:
        band1 = stretch_to_uint8(vv)
        return np.stack([band1, band1, band1], axis=0)

    vh = np.asarray(vh, dtype=np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(vh != 0, vv / vh, 0.0)
    band1 = stretch_to_uint8(vv)
    band2 = stretch_to_uint8(vh)
    band3 = stretch_to_uint8(ratio)
    return np.stack([band1, band2, band3], axis=0)


def build_rgb_like_geotiff(bands: Mapping[str, np.ndarray], transform, crs, out_path: str,
                            max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
    """Write the 3-band, size-capped GeoTIFF. Requires rasterio at call time.

    ``bands`` must contain at least ``"vv"``; ``"vh"`` is optional.
    ``transform``/``crs`` are the source raster's affine transform and CRS
    (e.g. from ``rasterio.open(...).transform`` / ``.crs``); they get
    rescaled to match any downsampling applied here.
    """
    try:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.warp import Affine
    except ImportError as exc:  # pragma: no cover - exercised only on the server
        raise RuntimeError("rasterio is required to write GeoTIFFs; install requirements.txt") from exc

    vv = np.asarray(bands["vv"])
    vh = bands.get("vh")
    height, width = vv.shape[-2], vv.shape[-1]

    plan = plan_downsample(width, height, max_bytes=max_bytes)
    stack = build_band_stack(vv, vh)  # (3, H, W) uint8 at native resolution

    if plan.scale < 1.0:
        from PIL import Image
        resized_bands = []
        for i in range(stack.shape[0]):
            img = Image.fromarray(stack[i])
            img = img.resize((plan.out_width, plan.out_height), Image.BILINEAR)
            resized_bands.append(np.asarray(img, dtype=np.uint8))
        stack = np.stack(resized_bands, axis=0)
        out_transform = transform * Affine.scale(1 / plan.scale, 1 / plan.scale)
    else:
        out_transform = transform

    profile = dict(
        driver="GTiff", dtype="uint8", count=stack.shape[0],
        width=stack.shape[2], height=stack.shape[1],
        crs=crs, transform=out_transform,
        compress="deflate", predictor=2, tiled=True,
        blockxsize=256, blockysize=256, interleave="pixel",
    )
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(stack)
        dst.descriptions = ("VV (stretched)", "VH (stretched)", "VV/VH ratio (pseudo-channel)")

    import os
    size_bytes = os.path.getsize(out_path)
    if size_bytes > max_bytes:
        # Compression beat our assumed ratio badly (rare, e.g. very noisy
        # scenes). Shrink once more using the *measured* ratio and retry.
        measured_ratio = size_bytes / max(plan.estimated_raw_bytes, 1)
        tighter = plan_downsample(width, height, max_bytes=max_bytes,
                                   compression_ratio=max(measured_ratio, 0.05))
        return build_rgb_like_geotiff(bands, transform, crs, out_path, max_bytes=max_bytes) \
            if tighter.scale < plan.scale else {
                "path": out_path, "size_bytes": size_bytes, "band_count": stack.shape[0],
                "width": stack.shape[2], "height": stack.shape[1], "within_budget": False,
            }

    return {
        "path": out_path, "size_bytes": size_bytes, "band_count": stack.shape[0],
        "width": stack.shape[2], "height": stack.shape[1], "within_budget": size_bytes <= max_bytes,
    }
