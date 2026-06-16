from __future__ import annotations

import html
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .fingerprint import analyze_image, color_thumbnail_delta, hamming_distance, thumbnail_delta
from .images import CropRegion, read_ppm, write_png
from .selection import AnalyzedFrame, FrameCluster, select_slide_frames
from .video import resolve_video_source, sample_video_frames


@dataclass(frozen=True)
class ExtractConfig:
    sample_interval: float = 2.0
    similarity_threshold: int = 20
    thumb_threshold: float = 10.0
    min_slide_score: float = 0.08
    min_stable_samples: int = 1
    start: float = 0.0
    end: float | None = None
    max_width: int = 1280
    crop: CropRegion | None = None
    allow_repeats: bool = False
    write_contact_sheet: bool = True
    keep_work_dir: bool = False
    ffmpeg: str = "ffmpeg"
    ytdlp: str = "yt-dlp"


@dataclass(frozen=True)
class SlideInfo:
    index: int
    file: str
    timestamp: float
    timestamp_label: str
    cluster_start: float
    cluster_end: float
    frames_in_cluster: int
    slide_score: float
    edge_density: float
    sharpness: float
    background_ratio: float
    contrast: float
    dhash: str


@dataclass(frozen=True)
class ExtractionResult:
    output_dir: Path
    manifest_path: Path
    slides: list[SlideInfo]
    sampled_frames: int
    analyzed_frames: int
    work_dir: Path | None


def extract_slides(source: str, output_dir: str | Path, config: ExtractConfig) -> ExtractionResult:
    output_dir = Path(output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"output path exists and is not a directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    temp_context = tempfile.TemporaryDirectory(prefix="youtube-slides-")
    work_dir = Path(temp_context.name)
    if config.keep_work_dir:
        temp_context.cleanup()
        work_dir = _next_work_dir(output_dir)
        work_dir.mkdir(parents=True)

    try:
        video_path = resolve_video_source(source, work_dir, ytdlp=config.ytdlp)
        sampled = sample_video_frames(
            video_path,
            work_dir / "frames",
            interval=config.sample_interval,
            start=config.start,
            end=config.end,
            max_width=config.max_width,
            ffmpeg=config.ffmpeg,
        )
        analyzed = [_analyze_sample(frame, config.crop) for frame in sampled]
        clusters = select_slide_frames(
            analyzed,
            min_slide_score=config.min_slide_score,
            min_stable_samples=config.min_stable_samples,
            similarity_threshold=config.similarity_threshold,
            thumb_threshold=config.thumb_threshold,
            allow_repeats=config.allow_repeats,
        )
        slides = _export_slides(clusters, output_dir, config.crop)
        manifest_path = _write_manifest(
            output_dir,
            source=source,
            video_path=video_path,
            config=config,
            slides=slides,
            sampled_frames=len(sampled),
            analyzed_frames=len(analyzed),
        )
        if config.write_contact_sheet:
            _write_contact_sheet(output_dir, slides)
        result = ExtractionResult(
            output_dir=output_dir,
            manifest_path=manifest_path,
            slides=slides,
            sampled_frames=len(sampled),
            analyzed_frames=len(analyzed),
            work_dir=work_dir if config.keep_work_dir else None,
        )
    finally:
        if not config.keep_work_dir:
            temp_context.cleanup()

    return result


def _analyze_sample(sample, crop: CropRegion | None) -> AnalyzedFrame:
    image = read_ppm(sample.path).crop(crop)
    fingerprint = analyze_image(image)
    return AnalyzedFrame(
        path=sample.path,
        index=sample.index,
        timestamp=sample.timestamp,
        fingerprint=fingerprint,
    )


def _export_slides(
    clusters: list[FrameCluster],
    output_dir: Path,
    crop: CropRegion | None,
) -> list[SlideInfo]:
    slides: list[SlideInfo] = []
    for slide_index, cluster in enumerate(clusters, start=1):
        frame = cluster.best_frame
        image = read_ppm(frame.path).crop(crop)
        filename = f"slide_{slide_index:03d}.png"
        write_png(output_dir / filename, image)
        fingerprint = frame.fingerprint
        slides.append(
            SlideInfo(
                index=slide_index,
                file=filename,
                timestamp=frame.timestamp,
                timestamp_label=format_timestamp(frame.timestamp),
                cluster_start=cluster.frames[0].timestamp,
                cluster_end=cluster.frames[-1].timestamp,
                frames_in_cluster=len(cluster.frames),
                slide_score=round(fingerprint.slide_score, 4),
                edge_density=round(fingerprint.edge_density, 4),
                sharpness=round(fingerprint.sharpness, 2),
                background_ratio=round(fingerprint.background_ratio, 4),
                contrast=round(fingerprint.contrast, 2),
                dhash=f"{fingerprint.dhash:x}",
            )
        )
    return slides


def _write_manifest(
    output_dir: Path,
    *,
    source: str,
    video_path: Path,
    config: ExtractConfig,
    slides: list[SlideInfo],
    sampled_frames: int,
    analyzed_frames: int,
) -> Path:
    manifest = {
        "source": source,
        "video_path": str(video_path),
        "sampled_frames": sampled_frames,
        "analyzed_frames": analyzed_frames,
        "slide_count": len(slides),
        "config": _config_to_json(config),
        "slides": [asdict(slide) for slide in slides],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _next_work_dir(output_dir: Path) -> Path:
    base = output_dir / "work"
    if not base.exists():
        return base
    for index in range(1, 1000):
        candidate = output_dir / f"work_{index:03d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"unable to find an unused work directory under {output_dir}")


def _write_contact_sheet(output_dir: Path, slides: list[SlideInfo]) -> Path:
    rows = []
    for slide in slides:
        rows.append(
            '<figure>'
            f'<img src="{html.escape(slide.file)}" alt="Slide {slide.index}">'
            f"<figcaption>{slide.index:03d} - {html.escape(slide.timestamp_label)}</figcaption>"
            "</figure>"
        )
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>youtube-slides contact sheet</title>
<style>
body {{ margin: 24px; font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2328; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; }}
figure {{ margin: 0; border: 1px solid #d8dee4; border-radius: 8px; overflow: hidden; background: #fff; }}
img {{ width: 100%; display: block; background: #f6f8fa; }}
figcaption {{ padding: 8px 10px; color: #57606a; }}
</style>
</head>
<body>
<main class="grid">
{''.join(rows)}
</main>
</body>
</html>
"""
    path = output_dir / "index.html"
    path.write_text(document, encoding="utf-8")
    return path


def _config_to_json(config: ExtractConfig) -> dict:
    data = asdict(config)
    if config.crop is not None:
        data["crop"] = asdict(config.crop)
    return data


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        whole += 1
        millis = 0
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def parse_timestamp(value: str) -> float:
    value = value.strip()
    if not value:
        raise ValueError("timestamp cannot be empty")
    if ":" not in value:
        return float(value)

    parts = value.split(":")
    if len(parts) > 3:
        raise ValueError(f"invalid timestamp: {value}")
    try:
        numeric = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value}") from exc

    total = 0.0
    for part in numeric:
        total = total * 60 + part
    return total


def frame_similarity_debug(left: AnalyzedFrame, right: AnalyzedFrame) -> dict[str, float | int]:
    return {
        "hamming": hamming_distance(left.fingerprint.dhash, right.fingerprint.dhash),
        "thumbnail_delta": thumbnail_delta(left.fingerprint.thumb_luma, right.fingerprint.thumb_luma),
        "color_delta": color_thumbnail_delta(left.fingerprint.thumb_rgb, right.fingerprint.thumb_rgb),
    }
