"""Small, inspectable colour and texture features; no coordinates or labels."""

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

FEATURE_VERSION = "rgb-hsv-histogram-texture-v1"
FEATURE_COUNT = 84
FloatArray = NDArray[np.float64]


def image_features(path: Path) -> FloatArray:
    with Image.open(path) as source:
        if source.size != (39, 39):
            raise ValueError(f"Expected a 39×39 survey crop, got {source.size}: {path}")
        if source.mode not in {"RGB", "RGBA"}:
            raise ValueError(f"Expected an RGB or RGBA crop: {path}")
        if source.mode == "RGBA" and source.getchannel("A").getextrema() != (255, 255):
            raise ValueError(f"Survey crops must be fully opaque, without nodata pixels: {path}")
        image = source.convert("RGB")
        rgb = np.asarray(image, dtype=np.float64) / 255
        hsv = np.asarray(image.convert("HSV"), dtype=np.float64) / 255
    channels = np.concatenate((rgb, hsv), axis=2).reshape(-1, 6)
    histograms = [
        np.histogram(channel, bins=8, range=(0, 1))[0] / len(channel) for channel in channels.T
    ]
    summaries = [
        channels.mean(axis=0),
        channels.std(axis=0),
        np.quantile(channels, (0.1, 0.5, 0.9), axis=0).ravel(),
        np.abs(np.diff(rgb, axis=0)).mean(axis=(0, 1)),
        np.abs(np.diff(rgb, axis=1)).mean(axis=(0, 1)),
    ]
    return np.concatenate(histograms + summaries)


def feature_matrix(paths: list[Path]) -> FloatArray:
    if not paths:
        raise ValueError("Need at least one image")
    return np.stack([image_features(path) for path in paths])
