from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .browser_cookies import ytdlp_cookie_cli_args, ytdlp_cookie_options
from .certificates import certificate_env, resolve_ca_bundle, temporary_certificate_env


@dataclass(frozen=True)
class SampledFrame:
    path: Path
    index: int
    timestamp: float


def is_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_video_source(
    source: str,
    work_dir: Path,
    *,
    ytdlp: str = "yt-dlp",
    cookie_browser: str | None = None,
) -> Path:
    source_path = Path(source).expanduser()
    if source_path.exists():
        return source_path

    if not is_url(source):
        raise FileNotFoundError(f"source is neither an existing file nor a URL: {source}")

    downloaded = _download_with_ytdlp(source, work_dir, ytdlp=ytdlp, cookie_browser=cookie_browser)
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


def _download_with_ytdlp(
    source: str,
    work_dir: Path,
    *,
    ytdlp: str,
    cookie_browser: str | None = None,
) -> Path | None:
    output_template = work_dir / "source.%(ext)s"
    ffmpeg_exe = resolve_ffmpeg_executable()
    ca_bundle = resolve_ca_bundle()

    if shutil.which(ytdlp):
        command = [
            ytdlp,
            "--no-playlist",
            "-f",
            "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
            "--merge-output-format",
            "mp4",
            "--ffmpeg-location",
            ffmpeg_exe,
            "-o",
            str(output_template),
            *ytdlp_cookie_cli_args(cookie_browser),
            source,
        ]
        _run(
            command,
            description="download video with yt-dlp",
            extra_env=certificate_env(ca_bundle),
        )
    else:
        try:
            import yt_dlp
        except Exception:
            return None
        options = {
            "noplaylist": True,
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
            "merge_output_format": "mp4",
            "ffmpeg_location": ffmpeg_exe,
            "outtmpl": str(output_template),
            "quiet": True,
            "no_warnings": True,
            **ytdlp_cookie_options(cookie_browser),
        }
        try:
            with temporary_certificate_env(ca_bundle):
                with yt_dlp.YoutubeDL(options) as downloader:
                    downloader.download([source])
        except Exception as exc:
            raise RuntimeError(f"unable to download video with bundled yt-dlp: {exc}") from exc

    candidates = sorted(
        [path for path in work_dir.glob("source.*") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _run(
    command: list[str],
    *,
    description: str,
    extra_env: dict[str, str] | None = None,
) -> None:
    env = None
    if extra_env:
        env = {**os.environ, **extra_env}

    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"unable to {description}: {command[0]} was not found") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        if detail:
            raise RuntimeError(f"unable to {description}: {detail}")
        raise RuntimeError(f"unable to {description}: exited with {completed.returncode}")
