from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .captions import CaptionCue, download_english_captions
from .narrative import build_caption_narratives, notes_by_slide_index
from .openai_narrative import DEFAULT_OPENAI_MODEL, generate_ai_narratives
from .pipeline import ExtractConfig, ExtractionResult, extract_slides
from .pptx_export import export_pptx, write_reading_view
from .video import is_url


LogCallback = Callable[[str], None]


@dataclass(frozen=True)
class DesktopJobConfig:
    source: str
    output_root: Path
    sample_interval: float = 2.0
    min_stable_samples: int = 2
    similarity_threshold: int = 20
    max_width: int = 1280
    narrative_mode: str = "captions"
    openai_api_key: str | None = None
    openai_model: str = DEFAULT_OPENAI_MODEL
    include_caption_notes: bool | None = None
    create_pptx: bool = True
    create_reading_view: bool = True


@dataclass(frozen=True)
class DesktopJobResult:
    job_dir: Path
    slides_dir: Path
    manifest_path: Path
    pptx_path: Path | None
    reading_view_path: Path | None
    extraction: ExtractionResult
    notes_count: int


def run_desktop_job(config: DesktopJobConfig, log: LogCallback | None = None) -> DesktopJobResult:
    logger = log or (lambda message: None)
    config.output_root.mkdir(parents=True, exist_ok=True)
    job_dir = _next_job_dir(config.output_root, config.source)
    slides_dir = job_dir / "slides"
    job_dir.mkdir(parents=True)

    logger(f"Output folder: {job_dir}")
    logger("Extracting unique slide frames...")
    extraction = extract_slides(
        config.source,
        slides_dir,
        ExtractConfig(
            sample_interval=config.sample_interval,
            min_stable_samples=config.min_stable_samples,
            similarity_threshold=config.similarity_threshold,
            max_width=config.max_width,
        ),
    )
    logger(f"Extracted {len(extraction.slides)} slides from {extraction.sampled_frames} sampled frames.")

    notes = _build_notes(config, extraction, job_dir, logger)

    pptx_path = None
    if config.create_pptx:
        pptx_path = job_dir / "lecture_slides.pptx"
        logger("Writing PowerPoint deck...")
        export_pptx(slides_dir, extraction.slides, pptx_path, notes=notes)
        logger(f"Wrote PowerPoint: {pptx_path}")

    reading_view_path = None
    if config.create_reading_view:
        reading_view_path = job_dir / "reading_view.html"
        logger("Writing HTML reading view...")
        write_reading_view(slides_dir, extraction.slides, reading_view_path, notes=notes)
        logger(f"Wrote reading view: {reading_view_path}")

    logger("Done.")
    return DesktopJobResult(
        job_dir=job_dir,
        slides_dir=slides_dir,
        manifest_path=extraction.manifest_path,
        pptx_path=pptx_path,
        reading_view_path=reading_view_path,
        extraction=extraction,
        notes_count=len(notes),
    )


def _build_notes(
    config: DesktopJobConfig,
    extraction: ExtractionResult,
    job_dir: Path,
    logger: LogCallback,
) -> dict[int, list[str] | str]:
    mode = _narrative_mode(config)
    if mode == "none":
        logger("Narrative notes are off.")
        return {}
    if not is_url(config.source):
        logger("Skipping narrative notes because the source is a local video file.")
        return {}

    logger("Downloading English captions for narrative notes...")
    cues = download_english_captions(config.source, job_dir / "captions")
    if not cues:
        logger("No English captions were found; the deck will not include notes.")
        return {}

    if mode == "ai":
        if not config.openai_api_key:
            raise ValueError("OpenAI API key is required when AI narrative generation is selected.")
        try:
            return _build_ai_notes(config, extraction, cues, logger)
        except Exception as exc:
            raise RuntimeError(f"AI narrative generation failed: {exc}") from exc

    narratives = build_caption_narratives(extraction.slides, cues)
    notes = notes_by_slide_index(narratives)
    logger(f"Added caption-derived notes for {len(notes)} slides.")
    return notes


def _build_ai_notes(
    config: DesktopJobConfig,
    extraction: ExtractionResult,
    cues: list[CaptionCue],
    logger: LogCallback,
) -> dict[int, list[str] | str]:
    result = generate_ai_narratives(
        extraction.slides,
        cues,
        api_key=config.openai_api_key or "",
        model=config.openai_model,
        log=logger,
    )
    notes = notes_by_slide_index(result.narratives)
    if result.usage.total_tokens is not None:
        logger(
            "OpenAI usage: "
            f"{result.usage.total_tokens} total tokens "
            f"({result.usage.input_tokens or 0} input, {result.usage.output_tokens or 0} output)."
        )
    logger(f"Added AI-generated narratives for {len(notes)} slides.")
    return notes


def _narrative_mode(config: DesktopJobConfig) -> str:
    if config.include_caption_notes is not None:
        return "captions" if config.include_caption_notes else "none"
    mode = config.narrative_mode.strip().lower()
    if mode not in {"none", "captions", "ai"}:
        raise ValueError(f"unknown narrative mode: {config.narrative_mode}")
    return mode


def _next_job_dir(output_root: Path, source: str) -> Path:
    stem = _slug_from_source(source)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    base = output_root / f"{stem}-{timestamp}"
    if not base.exists():
        return base
    for index in range(1, 100):
        candidate = output_root / f"{stem}-{timestamp}-{index:02d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"unable to create a unique job directory under {output_root}")


def _slug_from_source(source: str) -> str:
    if "watch?v=" in source:
        match = re.search(r"[?&]v=([A-Za-z0-9_-]+)", source)
        if match:
            return f"youtube-{match.group(1)}"
    path = Path(source)
    stem = path.stem if path.suffix else source
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-").lower()
    return stem[:48] or "lecture-slides"
