"""Shared video duration policy."""

from __future__ import annotations

from typing import Any, Iterable

MIN_VIDEO_DURATION_SECONDS = 5


def coerce_video_duration(value: Any, *, default: int = MIN_VIDEO_DURATION_SECONDS) -> int:
    """Return a generation-safe video duration.

    Boundary/review-only markers should be handled before calling this helper;
    real video generation must never be shorter than ``MIN_VIDEO_DURATION_SECONDS``.
    """
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = int(default)
    return max(MIN_VIDEO_DURATION_SECONDS, seconds)


def filter_supported_video_durations(durations: Iterable[Any]) -> list[int]:
    """Drop sub-minimum durations from model capabilities shown to authoring UI."""
    result: set[int] = set()
    for duration in durations:
        if isinstance(duration, bool):
            continue
        try:
            seconds = int(duration)
        except (TypeError, ValueError):
            continue
        if seconds >= MIN_VIDEO_DURATION_SECONDS:
            result.add(seconds)
    normalized = sorted(result)
    return normalized or [MIN_VIDEO_DURATION_SECONDS]


def pick_default_video_duration(durations: Iterable[Any] | None = None) -> int:
    """Pick the smallest supported duration that satisfies the project minimum."""
    return filter_supported_video_durations(durations or [MIN_VIDEO_DURATION_SECONDS])[0]


def coerce_video_duration_for_supported(value: Any, durations: Iterable[Any]) -> int:
    """Coerce a requested duration to the nearest supported value at or above 5s."""
    requested = coerce_video_duration(value)
    supported = filter_supported_video_durations(durations)
    if requested in supported:
        return requested
    larger = [duration for duration in supported if duration >= requested]
    return larger[0] if larger else supported[-1]
