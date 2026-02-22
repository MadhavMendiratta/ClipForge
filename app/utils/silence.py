"""Silence detection and removal utilities using ffmpeg."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Default silence detection parameters
SILENCE_THRESHOLD_DB = -30  # dB threshold for silence
MIN_SILENCE_DURATION = 0.5  # Minimum silence duration in seconds


def detect_silent_segments(
    input_path: Path,
    threshold_db: int = SILENCE_THRESHOLD_DB,
    min_duration: float = MIN_SILENCE_DURATION,
) -> list[tuple[float, float]]:
    """
    Detect silent segments in a video using ffmpeg's silencedetect filter.

    Args:
        input_path: Path to the video file.
        threshold_db: Volume threshold in dB below which audio is considered silent.
        min_duration: Minimum duration of silence to detect (seconds).

    Returns:
        List of (start, end) tuples representing silent segments.
    """
    result = subprocess.run(
        [
            "ffmpeg",
            "-i", str(input_path),
            "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
            "-f", "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )

    # silencedetect outputs to stderr
    output = result.stderr
    silence_starts: list[float] = []
    silence_ends: list[float] = []

    for line in output.split("\n"):
        start_match = re.search(r"silence_start:\s*([\d.]+)", line)
        if start_match:
            silence_starts.append(float(start_match.group(1)))

        end_match = re.search(r"silence_end:\s*([\d.]+)", line)
        if end_match:
            silence_ends.append(float(end_match.group(1)))

    # Pair up starts and ends
    segments: list[tuple[float, float]] = []
    for i, start in enumerate(silence_starts):
        if i < len(silence_ends):
            segments.append((start, silence_ends[i]))
        else:
            # Silence extends to end of file — estimate end from duration
            segments.append((start, _get_duration(input_path)))

    logger.info("Detected %d silent segments in %s", len(segments), input_path.name)
    return segments


def _get_duration(input_path: Path) -> float:
    """Get video duration via ffprobe."""
    from app.utils.ffmpeg_ops import get_video_duration

    return get_video_duration(input_path)


def _compute_non_silent_segments(
    silent_segments: list[tuple[float, float]], total_duration: float
) -> list[tuple[float, float]]:
    """
    Compute the inverse of silent segments — i.e. the non-silent (audible) parts.

    Args:
        silent_segments: List of (start, end) silent segment tuples.
        total_duration: Total duration of the video.

    Returns:
        List of (start, end) tuples for non-silent segments.
    """
    if not silent_segments:
        return [(0, total_duration)]

    non_silent: list[tuple[float, float]] = []
    prev_end = 0.0

    for sil_start, sil_end in sorted(silent_segments, key=lambda x: x[0]):
        if sil_start > prev_end:
            non_silent.append((prev_end, sil_start))
        prev_end = max(prev_end, sil_end)

    if prev_end < total_duration:
        non_silent.append((prev_end, total_duration))

    return non_silent


def remove_silence(
    input_path: Path,
    output_path: Path,
    progress_callback: Optional[Callable[[float], None]] = None,
    threshold_db: int = SILENCE_THRESHOLD_DB,
    min_duration: float = MIN_SILENCE_DURATION,
) -> None:
    """
    Remove silent segments from a video.

    Steps:
        1. Detect silent segments using silencedetect.
        2. Compute non-silent segments.
        3. Build ffmpeg filter_complex to select and concatenate non-silent parts.

    Args:
        input_path: Path to the input video.
        output_path: Path for the output video.
        progress_callback: Optional callback receiving progress percentage (0-100).
        threshold_db: Volume threshold in dB.
        min_duration: Minimum silence duration in seconds.
    """
    if progress_callback:
        progress_callback(10)

    # Step 1: Detect silence
    silent_segments = detect_silent_segments(input_path, threshold_db, min_duration)

    if progress_callback:
        progress_callback(30)

    if not silent_segments:
        logger.info("No silent segments detected, copying original")
        import shutil
        shutil.copy2(input_path, output_path)
        if progress_callback:
            progress_callback(100)
        return

    # Step 2: Compute non-silent segments
    total_duration = _get_duration(input_path)
    non_silent = _compute_non_silent_segments(silent_segments, total_duration)

    if not non_silent:
        logger.warning("No non-silent segments found — copying original")
        import shutil
        shutil.copy2(input_path, output_path)
        if progress_callback:
            progress_callback(100)
        return

    if progress_callback:
        progress_callback(50)

    # Step 3: Build ffmpeg filter to select and concatenate non-silent parts
    n = len(non_silent)
    filter_parts: list[str] = []
    concat_inputs = ""

    for i, (start, end) in enumerate(non_silent):
        duration = end - start
        filter_parts.append(
            f"[0:v]trim=start={start}:duration={duration},setpts=PTS-STARTPTS[v{i}];"
        )
        filter_parts.append(
            f"[0:a]atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS[a{i}];"
        )
        concat_inputs += f"[v{i}][a{i}]"

    filter_complex = "".join(filter_parts)
    filter_complex += f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        str(output_path),
    ]

    logger.info("Running silence removal with %d non-silent segments", n)
    logger.debug("ffmpeg command: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg silence removal failed: {result.stderr[-500:]}")

    if progress_callback:
        progress_callback(100)

    logger.info(
        "Silence removal complete: removed %d silent segments, kept %d segments",
        len(silent_segments),
        n,
    )
