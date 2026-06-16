from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable


@dataclass(frozen=True)
class CropRegion:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def parse(cls, value: str) -> "CropRegion":
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 4:
            raise ValueError("crop must have four comma-separated integers: x,y,w,h")
        try:
            x, y, width, height = [int(part) for part in parts]
        except ValueError as exc:
            raise ValueError("crop must have four comma-separated integers: x,y,w,h") from exc
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError("crop values must be non-negative, with positive width and height")
        return cls(x=x, y=y, width=width, height=height)


@dataclass(frozen=True)
class RgbImage:
    width: int
    height: int
    data: bytes

    def __post_init__(self) -> None:
        expected = self.width * self.height * 3
        if len(self.data) != expected:
            raise ValueError(f"expected {expected} RGB bytes, got {len(self.data)}")

    def crop(self, region: CropRegion | None) -> "RgbImage":
        if region is None:
            return self
        if region.x + region.width > self.width or region.y + region.height > self.height:
            raise ValueError(
                f"crop {region.x},{region.y},{region.width},{region.height} exceeds "
                f"image size {self.width}x{self.height}"
            )

        row_stride = self.width * 3
        start_x = region.x * 3
        end_x = (region.x + region.width) * 3
        rows = []
        for y in range(region.y, region.y + region.height):
            row_start = y * row_stride
            rows.append(self.data[row_start + start_x : row_start + end_x])
        return RgbImage(region.width, region.height, b"".join(rows))

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        offset = (y * self.width + x) * 3
        return self.data[offset], self.data[offset + 1], self.data[offset + 2]

    def sampled_luma(self, width: int, height: int) -> list[int]:
        values: list[int] = []
        for ty in range(height):
            y = min(self.height - 1, int((ty + 0.5) * self.height / height))
            for tx in range(width):
                x = min(self.width - 1, int((tx + 0.5) * self.width / width))
                r, g, b = self.pixel(x, y)
                values.append(luma(r, g, b))
        return values

    def sampled_rgb(self, width: int, height: int) -> list[tuple[int, int, int]]:
        values: list[tuple[int, int, int]] = []
        for ty in range(height):
            y = min(self.height - 1, int((ty + 0.5) * self.height / height))
            for tx in range(width):
                x = min(self.width - 1, int((tx + 0.5) * self.width / width))
                values.append(self.pixel(x, y))
        return values


def luma(r: int, g: int, b: int) -> int:
    return (299 * r + 587 * g + 114 * b) // 1000


def read_ppm(path: str | Path) -> RgbImage:
    with Path(path).open("rb") as handle:
        magic = _read_token(handle)
        if magic != b"P6":
            raise ValueError(f"{path} is not a binary PPM (P6) file")
        width = int(_read_token(handle))
        height = int(_read_token(handle))
        max_value = int(_read_token(handle))
        if max_value != 255:
            raise ValueError(f"{path} uses unsupported PPM max value {max_value}")
        data = handle.read(width * height * 3)
        if len(data) != width * height * 3:
            raise ValueError(f"{path} ended before all pixel data was read")
    return RgbImage(width, height, data)


def write_ppm(path: str | Path, image: RgbImage) -> None:
    path = Path(path)
    with path.open("wb") as handle:
        handle.write(f"P6\n{image.width} {image.height}\n255\n".encode("ascii"))
        handle.write(image.data)


def write_png(path: str | Path, image: RgbImage) -> None:
    path = Path(path)
    row_stride = image.width * 3
    raw_rows = []
    for y in range(image.height):
        row_start = y * row_stride
        raw_rows.append(b"\x00" + image.data[row_start : row_start + row_stride])
    raw = b"".join(raw_rows)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind)
        crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)

    png = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(raw, level=6)),
            chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(png)


def _read_token(handle: BinaryIO) -> bytes:
    token = bytearray()
    while True:
        char = handle.read(1)
        if char == b"":
            raise ValueError("unexpected end of PPM header")
        if char.isspace():
            continue
        if char == b"#":
            handle.readline()
            continue
        token.extend(char)
        break

    while True:
        char = handle.read(1)
        if char == b"":
            break
        if char.isspace():
            break
        if char == b"#":
            handle.readline()
            break
        token.extend(char)
    return bytes(token)


def mean(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    return total / count if count else 0.0


def variance(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


def rms(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += value * value
        count += 1
    return math.sqrt(total / count) if count else 0.0
