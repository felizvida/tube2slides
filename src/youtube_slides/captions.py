from __future__ import annotations

import html
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .browser_cookies import ytdlp_cookie_options
from .certificates import resolve_ca_bundle, temporary_certificate_env


@dataclass(frozen=True)
class CaptionCue:
    start: float
    end: float
    text: str


_TIMING_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})"
)
_TAG_RE = re.compile(r"<[^>]+>")
_VOICE_RE = re.compile(r"^\s*<v\s+[^>]+>", re.IGNORECASE)


def download_english_captions(
    source_url: str,
    work_dir: str | Path | None = None,
    *,
    cookie_browser: str | None = None,
) -> list[CaptionCue]:
    """Download English subtitles/auto-captions for a YouTube URL with yt-dlp."""

    try:
        import yt_dlp
    except Exception as exc:
        raise RuntimeError("yt-dlp is required to download captions") from exc

    cleanup_context = None
    if work_dir is None:
        cleanup_context = tempfile.TemporaryDirectory(prefix="youtube-slides-captions-")
        work_path = Path(cleanup_context.name)
    else:
        work_path = Path(work_dir)
        work_path.mkdir(parents=True, exist_ok=True)

    try:
        outtmpl = str(work_path / "captions.%(ext)s")
        options = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en.*"],
            "subtitlesformat": "vtt",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            **ytdlp_cookie_options(cookie_browser),
        }
        with temporary_certificate_env(resolve_ca_bundle()):
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([source_url])

        caption_files = sorted(work_path.glob("captions*.vtt"))
        if not caption_files:
            return []
        return parse_vtt(caption_files[0].read_text(encoding="utf-8", errors="replace"))
    finally:
        if cleanup_context is not None:
            cleanup_context.cleanup()


def parse_vtt(content: str) -> list[CaptionCue]:
    cues: list[CaptionCue] = []
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n"))
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = _TIMING_RE.search(lines[timing_index])
        if not match:
            continue

        text_lines = lines[timing_index + 1 :]
        text = _clean_caption_text(" ".join(text_lines))
        if not text:
            continue
        cue = CaptionCue(
            start=_parse_vtt_timestamp(match.group("start")),
            end=_parse_vtt_timestamp(match.group("end")),
            text=text,
        )
        if cues and cue.text == cues[-1].text and abs(cue.start - cues[-1].start) < 0.75:
            continue
        cues.append(cue)
    return _collapse_repeated_youtube_cues(cues)


def cues_in_range(cues: list[CaptionCue], start: float, end: float) -> list[CaptionCue]:
    return [cue for cue in cues if cue.end > start and cue.start < end]


def transcript_for_range(
    cues: list[CaptionCue],
    start: float,
    end: float,
    *,
    max_words: int = 170,
) -> str:
    selected = cues_in_range(cues, start, end)
    words: list[str] = []
    for cue in selected:
        cue_words = cue.text.split()
        if words and cue_words and _same_tail(words, cue_words):
            continue
        words.extend(cue_words)
        if len(words) >= max_words:
            return " ".join(words[:max_words]).rstrip() + " ..."
    return " ".join(words).strip()


def _parse_vtt_timestamp(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def _clean_caption_text(value: str) -> str:
    value = _VOICE_RE.sub("", value)
    value = _TAG_RE.sub("", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _collapse_repeated_youtube_cues(cues: list[CaptionCue]) -> list[CaptionCue]:
    collapsed: list[CaptionCue] = []
    for cue in cues:
        if collapsed and cue.text.startswith(collapsed[-1].text):
            collapsed[-1] = CaptionCue(
                start=collapsed[-1].start,
                end=cue.end,
                text=cue.text,
            )
            continue
        if collapsed and collapsed[-1].text.startswith(cue.text):
            continue
        collapsed.append(cue)
    return collapsed


def _same_tail(existing_words: list[str], next_words: list[str]) -> bool:
    if not existing_words or not next_words:
        return False
    overlap = min(len(existing_words), len(next_words), 8)
    return existing_words[-overlap:] == next_words[:overlap]
