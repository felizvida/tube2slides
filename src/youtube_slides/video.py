from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class SampledFrame:
    path: Path
    index: int
    timestamp: float


def is_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_video_source(source: str, work_dir: Path, *, ytdlp: str = "yt-dlp") -> Path:
    source_path = Path(source).expanduser()
    if source_path.exists():
        return source_path

    if not is_url(source):
        raise FileNotFoundError(f"source is neither an existing file nor a URL: {source}")

    downloaded = _download_with_ytdlp(source, work_dir, ytdlp=ytdlp)
    if downloaded is None:
        raise RuntimeError(
            "yt-dlp is required for YouTube URLs. Install it or pass a local video file."
        )
    return downloaded


def sample_video_frames(
    video_path: Path,
    frames_dir: Path,
    *,
    interval: float,
    start: float,
    end: float | None,
    max_width: int,
    ffmpeg: str = "ffmpeg",
) -> list[SampledFrame]:
    if interval <= 0:
        raise ValueError("sample interval must be positive")
    if end is not None and end <= start:
        raise ValueError("end must be greater than start")

    frames_dir.mkdir(parents=True, exist_ok=True)
    output_template = frames_dir / "frame_%06d.ppm"
    fps_expr = f"fps=1/{interval:g}"
    filters = [fps_expr]
    if max_width > 0:
        filters.append(f"scale={max_width}:-2:force_original_aspect_ratio=decrease")

    ffmpeg_exe = resolve_ffmpeg_executable(ffmpeg)
    command = [
        ffmpeg_exe,
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    if start > 0:
        command.extend(["-ss", f"{start:g}"])
    command.extend(["-i", str(video_path)])
    if end is not None:
        command.extend(["-t", f"{end - start:g}"])
    command.extend(
        [
            "-vf",
            ",".join(filters),
            "-pix_fmt",
            "rgb24",
            "-f",
            "image2",
            str(output_template),
        ]
    )
    _run(command, description="extract sampled frames with ffmpeg")

    frame_paths = sorted(frames_dir.glob("frame_*.ppm"))
    return [
        SampledFrame(path=path, index=index, timestamp=start + (index - 1) * interval)
        for index, path in enumerate(frame_paths, start=1)
    ]


def require_binaries(*names: str) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"missing required executable(s): {', '.join(missing)}")


def resolve_ffmpeg_executable(ffmpeg: str = "ffmpeg") -> str:
    if ffmpeg and ffmpeg != "ffmpeg":
        return ffmpeg
    discovered = shutil.which("ffmpeg")
    if discovered:
        return discovered
    try:
        import imageio_ffmpeg
    except Exception:
        return ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _download_with_ytdlp(source: str, work_dir: Path, *, ytdlp: str) -> Path | None:
    command_prefix: list[str]
    if shutil.which(ytdlp):
        command_prefix = [ytdlp]
    else:
        try:
            import yt_dlp  # noqa: F401
        except Exception:
            return None
        command_prefix = [sys.executable, "-m", "yt_dlp"]

    output_template = work_dir / "source.%(ext)s"
    command = [
        *command_prefix,
        "--no-playlist",
        "-f",
        "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(output_template),
        source,
    ]
    try:
        _run(command, description="download video with yt-dlp")
    except RuntimeError:
        if command_prefix[:2] == ["python3", "-m"]:
            return None
        raise

    candidates = sorted(
        [path for path in work_dir.glob("source.*") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _run(command: list[str], *, description: str) -> None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"unable to {description}: {command[0]} was not found") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        if detail:
            raise RuntimeError(f"unable to {description}: {detail}")
        raise RuntimeError(f"unable to {description}: exited with {completed.returncode}")
