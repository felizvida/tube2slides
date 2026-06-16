from __future__ import annotations

from dataclasses import dataclass

from .images import RgbImage, luma, mean, rms, variance


@dataclass(frozen=True)
class ImageFingerprint:
    dhash: int
    thumb_luma: tuple[int, ...]
    thumb_rgb: tuple[int, ...]
    edge_density: float
    sharpness: float
    background_ratio: float
    contrast: float
    slide_score: float


def analyze_image(image: RgbImage) -> ImageFingerprint:
    thumb_luma = tuple(image.sampled_luma(16, 9))
    thumb_rgb = _rgb_signature(image)
    edge_density = _edge_density(image)
    sharpness = _sharpness(image)
    background_ratio = _background_ratio(image)
    contrast = rms(value - mean(thumb_luma) for value in thumb_luma)
    slide_score = _slide_score(
        edge_density=edge_density,
        sharpness=sharpness,
        background_ratio=background_ratio,
        contrast=contrast,
    )
    return ImageFingerprint(
        dhash=_dhash(image),
        thumb_luma=thumb_luma,
        thumb_rgb=thumb_rgb,
        edge_density=edge_density,
        sharpness=sharpness,
        background_ratio=background_ratio,
        contrast=contrast,
        slide_score=slide_score,
    )


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def thumbnail_delta(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("thumbnail signatures must have the same length")
    return sum(abs(a - b) for a, b in zip(left, right)) / len(left)


def color_thumbnail_delta(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    return thumbnail_delta(left, right)


def fingerprints_are_similar(
    left: ImageFingerprint,
    right: ImageFingerprint,
    hash_threshold: int,
    thumb_threshold: float,
) -> bool:
    hash_delta = hamming_distance(left.dhash, right.dhash)
    luma_delta = thumbnail_delta(left.thumb_luma, right.thumb_luma)
    color_delta = color_thumbnail_delta(left.thumb_rgb, right.thumb_rgb)
    if (
        hash_delta <= hash_threshold
        and luma_delta <= thumb_threshold * 1.8
        and color_delta <= thumb_threshold * 1.6
    ):
        return True
    return (
        hash_delta <= hash_threshold * 2
        and luma_delta <= thumb_threshold
        and color_delta <= thumb_threshold * 1.2
    )


def _dhash(image: RgbImage, width: int = 17, height: int = 16) -> int:
    values = image.sampled_luma(width, height)
    result = 0
    for y in range(height):
        row = y * width
        for x in range(width - 1):
            result <<= 1
            if values[row + x] > values[row + x + 1]:
                result |= 1
    return result


def _rgb_signature(image: RgbImage, width: int = 16, height: int = 9) -> tuple[int, ...]:
    values: list[int] = []
    for r, g, b in image.sampled_rgb(width, height):
        values.extend((r, g, b))
    return tuple(values)


def _edge_density(image: RgbImage) -> float:
    width = 96
    height = 54
    values = image.sampled_luma(width, height)
    edges = 0
    total = 0
    for y in range(height - 1):
        row = y * width
        next_row = (y + 1) * width
        for x in range(width - 1):
            gx = abs(values[row + x] - values[row + x + 1])
            gy = abs(values[row + x] - values[next_row + x])
            if max(gx, gy) >= 32:
                edges += 1
            total += 1
    return edges / total if total else 0.0


def _sharpness(image: RgbImage) -> float:
    width = 80
    height = 45
    values = image.sampled_luma(width, height)
    laplacian_values: list[float] = []
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            center = values[row + x] * 4
            neighbors = (
                values[row + x - 1]
                + values[row + x + 1]
                + values[row - width + x]
                + values[row + width + x]
            )
            laplacian_values.append(center - neighbors)
    return variance(laplacian_values)


def _background_ratio(image: RgbImage) -> float:
    samples = image.sampled_rgb(80, 45)
    neutral_extremes = 0
    for r, g, b in samples:
        lum = luma(r, g, b)
        saturation_proxy = max(r, g, b) - min(r, g, b)
        if saturation_proxy <= 32 and (lum >= 224 or lum <= 42):
            neutral_extremes += 1
    return neutral_extremes / len(samples) if samples else 0.0


def _slide_score(
    *,
    edge_density: float,
    sharpness: float,
    background_ratio: float,
    contrast: float,
) -> float:
    edge_component = min(1.0, edge_density / 0.16)
    sharp_component = min(1.0, sharpness / 2600.0)
    background_component = min(1.0, background_ratio / 0.35)
    contrast_component = min(1.0, contrast / 55.0)

    score = (
        0.36 * edge_component
        + 0.24 * sharp_component
        + 0.24 * background_component
        + 0.16 * contrast_component
    )

    if edge_density < 0.003 or contrast < 6:
        score *= 0.25
    return max(0.0, min(1.0, score))
