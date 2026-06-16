from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .captions import CaptionCue, transcript_for_range
from .narrative import SlideNarrative
from .pipeline import SlideInfo


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.5"

LogCallback = Callable[[str], None]


@dataclass(frozen=True)
class AiNarrativeUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AiNarrativeResult:
    narratives: list[SlideNarrative]
    usage: AiNarrativeUsage


def generate_ai_narratives(
    slides: list[SlideInfo],
    cues: list[CaptionCue],
    *,
    api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
    log: LogCallback | None = None,
) -> AiNarrativeResult:
    if not api_key.strip():
        raise ValueError("An OpenAI API key is required for AI narrative generation.")
    if not slides:
        return AiNarrativeResult([], AiNarrativeUsage())

    segments = _caption_segments(slides, cues)
    segments_with_text = [segment for segment in segments if segment["caption"].strip()]
    if not segments_with_text:
        return AiNarrativeResult([], AiNarrativeUsage())

    logger = log or (lambda message: None)
    logger(f"Generating AI narratives for {len(segments)} slides with {model}...")
    payload = _responses_payload(model, segments)
    response = _post_responses_request(api_key, payload)
    text = extract_response_text(response)
    parsed = parse_narrative_json(text)
    narratives = _narratives_from_response(slides, parsed)
    usage = _usage_from_response(response)
    return AiNarrativeResult(narratives, usage)


def extract_response_text(response: dict[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
            elif isinstance(text, dict) and isinstance(text.get("value"), str):
                chunks.append(text["value"])
    return "\n".join(chunks).strip()


def parse_narrative_json(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        return []

    candidate = _strip_code_fence(text.strip())
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", candidate, re.DOTALL)
        if not match:
            raise ValueError("OpenAI returned text, but it was not valid JSON.")
        parsed = json.loads(match.group(1))

    if isinstance(parsed, dict):
        parsed = parsed.get("slides", [])
    if not isinstance(parsed, list):
        raise ValueError("OpenAI returned JSON that does not contain a slide list.")
    return [item for item in parsed if isinstance(item, dict)]


def _caption_segments(slides: list[SlideInfo], cues: list[CaptionCue]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for index, slide in enumerate(slides):
        next_start = slides[index + 1].timestamp if index + 1 < len(slides) else slide.timestamp + 120
        if next_start <= slide.timestamp:
            next_start = slide.timestamp + 120
        caption = transcript_for_range(cues, slide.timestamp, next_start, max_words=220)
        segments.append(
            {
                "slide_index": slide.index,
                "timestamp": slide.timestamp_label,
                "caption": caption,
            }
        )
    return segments


def _responses_payload(model: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["slides"],
        "properties": {
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["slide_index", "notes"],
                    "properties": {
                        "slide_index": {"type": "integer"},
                        "notes": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 4,
                            "items": {"type": "string"},
                        },
                    },
                },
            }
        },
    }
    instructions = (
        "You write concise speaker notes for an educational slide deck. "
        "Use only the supplied caption excerpts. Do not invent equations, citations, "
        "results, or claims that are not grounded in the captions. Each slide should "
        "get one to three short paragraphs that help a reader understand what the "
        "lecturer is explaining at that point."
    )
    user_input = {
        "task": "Create narrative notes for each slide from caption excerpts. Return JSON only.",
        "slides": segments,
    }
    return {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(user_input, ensure_ascii=False),
        "max_output_tokens": min(12000, max(1800, len(segments) * 160)),
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "slide_narratives",
                "strict": True,
                "schema": schema,
            }
        },
    }


def _post_responses_request(api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc


def _narratives_from_response(
    slides: list[SlideInfo],
    parsed: list[dict[str, Any]],
) -> list[SlideNarrative]:
    slide_indices = {slide.index for slide in slides}
    narratives: list[SlideNarrative] = []
    for item in parsed:
        try:
            slide_index = int(item.get("slide_index"))
        except (TypeError, ValueError):
            continue
        if slide_index not in slide_indices:
            continue

        raw_notes = item.get("notes", [])
        if isinstance(raw_notes, str):
            note_lines = [raw_notes]
        elif isinstance(raw_notes, list):
            note_lines = [str(line).strip() for line in raw_notes if str(line).strip()]
        else:
            note_lines = []
        if not note_lines:
            continue
        narratives.append(
            SlideNarrative(
                slide_index=slide_index,
                title=f"Slide {slide_index:03d} AI narrative",
                notes=["Narrative:", *note_lines],
            )
        )
    return narratives


def _usage_from_response(response: dict[str, Any]) -> AiNarrativeUsage:
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        return AiNarrativeUsage()
    return AiNarrativeUsage(
        input_tokens=_maybe_int(usage.get("input_tokens")),
        output_tokens=_maybe_int(usage.get("output_tokens")),
        total_tokens=_maybe_int(usage.get("total_tokens")),
    )


def _maybe_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _strip_code_fence(text: str) -> str:
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
