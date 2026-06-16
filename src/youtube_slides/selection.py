from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .fingerprint import ImageFingerprint, fingerprints_are_similar


@dataclass(frozen=True)
class AnalyzedFrame:
    path: Path
    index: int
    timestamp: float
    fingerprint: ImageFingerprint


@dataclass
class FrameCluster:
    frames: list[AnalyzedFrame] = field(default_factory=list)

    @property
    def representative(self) -> AnalyzedFrame:
        if not self.frames:
            raise ValueError("empty cluster has no representative")
        return self.best_frame

    @property
    def best_frame(self) -> AnalyzedFrame:
        if not self.frames:
            raise ValueError("empty cluster has no best frame")
        return max(
            self.frames,
            key=lambda frame: (
                frame.fingerprint.slide_score,
                frame.fingerprint.sharpness,
                -abs(frame.timestamp - self.midpoint_timestamp),
            ),
        )

    @property
    def midpoint_timestamp(self) -> float:
        if not self.frames:
            return 0.0
        return (self.frames[0].timestamp + self.frames[-1].timestamp) / 2


def select_slide_frames(
    frames: list[AnalyzedFrame],
    *,
    min_slide_score: float,
    min_stable_samples: int,
    similarity_threshold: int,
    thumb_threshold: float,
    allow_repeats: bool,
) -> list[FrameCluster]:
    clusters: list[FrameCluster] = []
    current = FrameCluster()

    for frame in frames:
        if frame.fingerprint.slide_score < min_slide_score:
            if current.frames:
                _append_if_stable(clusters, current, min_stable_samples)
                current = FrameCluster()
            continue

        if not current.frames:
            current.frames.append(frame)
            continue

        if fingerprints_are_similar(
            current.representative.fingerprint,
            frame.fingerprint,
            hash_threshold=similarity_threshold,
            thumb_threshold=thumb_threshold,
        ):
            current.frames.append(frame)
            continue

        _append_if_stable(clusters, current, min_stable_samples)
        current = FrameCluster(frames=[frame])

    if current.frames:
        _append_if_stable(clusters, current, min_stable_samples)

    if allow_repeats:
        return clusters
    return _drop_repeated_clusters(
        clusters,
        similarity_threshold=similarity_threshold,
        thumb_threshold=thumb_threshold,
    )


def _append_if_stable(
    clusters: list[FrameCluster],
    cluster: FrameCluster,
    min_stable_samples: int,
) -> None:
    if len(cluster.frames) >= min_stable_samples:
        clusters.append(cluster)


def _drop_repeated_clusters(
    clusters: list[FrameCluster],
    *,
    similarity_threshold: int,
    thumb_threshold: float,
) -> list[FrameCluster]:
    unique: list[FrameCluster] = []
    for cluster in clusters:
        best = cluster.best_frame
        duplicate_found = False
        for existing in unique:
            if fingerprints_are_similar(
                existing.best_frame.fingerprint,
                best.fingerprint,
                hash_threshold=similarity_threshold,
                thumb_threshold=thumb_threshold,
            ):
                duplicate_found = True
                break
        if not duplicate_found:
            unique.append(cluster)
    return unique
