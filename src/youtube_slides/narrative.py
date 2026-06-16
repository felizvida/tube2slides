from __future__ import annotations

from dataclasses import dataclass

from .captions import CaptionCue, transcript_for_range
from .pipeline import SlideInfo


@dataclass(frozen=True)
class SlideNarrative:
    slide_index: int
    title: str
    notes: list[str]


def build_caption_narratives(
    slides: list[SlideInfo],
    cues: list[CaptionCue],
    *,
    video_end: float | None = None,
) -> list[SlideNarrative]:
    narratives: list[SlideNarrative] = []
    for index, slide in enumerate(slides):
        next_start = (
            slides[index + 1].timestamp
            if index + 1 < len(slides)
            else video_end or slide.timestamp + 120
        )
        if next_start <= slide.timestamp:
            next_start = slide.timestamp + 120
        transcript = transcript_for_range(cues, slide.timestamp, next_start)
        title = f"Slide {slide.index:03d} context"
        if transcript:
            notes = [
                "Narrative:",
                (
                    "Use this slide as a visual anchor for the lecture segment "
                    f"around {slide.timestamp_label}. The accompanying explanation "
                    "from the captions is:"
                ),
                transcript,
            ]
        else:
            notes = [
                "Narrative:",
                (
                    "Use this slide as a visual anchor for this part of the lecture. "
                    "No English captions were available for this exact interval, so "
                    "review the slide content directly and treat it as a section marker."
                ),
            ]
        narratives.append(SlideNarrative(slide.index, title, notes))
    return narratives


def notes_by_slide_index(narratives: list[SlideNarrative]) -> dict[int, list[str]]:
    return {narrative.slide_index: narrative.notes for narrative in narratives}
