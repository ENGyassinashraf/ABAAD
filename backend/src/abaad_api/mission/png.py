"""Minimal dependency-free PNG encoder and terrain map rendering."""

from __future__ import annotations

import struct
import zlib

import numpy as np

from .terrain import Terrain, hillshade


def encode_png(rgb: np.ndarray) -> bytes:
    """Encode an (H, W, 3) uint8 array, row 0 at the TOP."""
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[r].tobytes() for r in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _north_up(a: np.ndarray) -> np.ndarray:
    return a[::-1]


def terrain_rgb(t: Terrain, layer: str = "hillshade", vis: np.ndarray | None = None,
                max_slope_deg: float = 20.0, scale: int = 2) -> np.ndarray:
    shade = hillshade(t)
    zn = (t.z - t.z.min()) / max(1e-9, float(np.ptp(t.z)))
    base = np.stack([0.30 + 0.55 * shade + 0.10 * zn] * 3, axis=-1)
    base[..., 0] *= 1.00
    base[..., 1] *= 0.97
    base[..., 2] *= 0.92
    if layer == "slope":
        s = np.clip(t.slope_deg / max_slope_deg, 0, 1.5)
        over = np.stack([np.clip(s, 0, 1), np.clip(1.2 - s, 0, 1) * 0.8, 0.25 * np.ones_like(s)], axis=-1)
        base = 0.45 * base + 0.55 * over
        base[t.slope_deg > max_slope_deg] = [0.55, 0.12, 0.10]
    elif layer == "visibility" and vis is not None:
        tint = np.zeros_like(base)
        tint[vis == 1] = [0.36, 0.60, 0.40]
        tint[vis == 0] = [0.55, 0.25, 0.20]
        tint[vis == 2] = [0.35, 0.35, 0.40]
        base = 0.5 * base + 0.5 * tint
    base[t.nogo] = [0.25, 0.10, 0.10]
    img = (np.clip(_north_up(base), 0, 1) * 255).astype(np.uint8)
    if scale > 1:
        img = np.kron(img, np.ones((scale, scale, 1), dtype=np.uint8))
    return img


def terrain_png(t: Terrain, layer: str = "hillshade", vis=None, max_slope_deg: float = 20.0, scale: int = 2) -> bytes:
    return encode_png(terrain_rgb(t, layer, vis, max_slope_deg, scale))
