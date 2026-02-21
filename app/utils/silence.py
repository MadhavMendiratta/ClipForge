"""Silence detection and removal utilities using ffmpeg."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from app.utils.ffmpeg_ops import get_video_duration

logger = logging.getLogger(__name__)

SILENCE_THRESHOLD_DB = -30
MIN_SILENCE_DURATION = 0.5


def detect_silent_segments(
    input_path: Path,
    threshold_db: int = SILENCE_THRESHOLD_DB,
    min_duration: float = MIN_SILENCE_DURATION,
) -> list[tuple[float, float]]:

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

    output = result.stderr

    silence_starts: list[float] = []
    silence_ends: list[float] = []

    for line in output.splitlines():
        start_match = re.search(r"silence_start:\s*([\d.]+)", line)
        if start_match:
            silence_starts.append(float(start_match.group(1)))

        end_match = re.search(r"silence_end:\s*([\d.]+)", line)
        if end_match:
            silence_ends.append(float(end_match.group(1)))

    segments: list[tuple[float, float]] = []

    total_duration = get_video_duration(input_path)

    for i, start in enumerate(silence_starts):
        if i < len(silence_ends):
            end = silence_ends[i]
        else:
            end = total_duration

        if end > start:
            segments.append((start, min(end, total_duration)))

    logger.info("Detected %d silent segments", len(segments))
    return segments


def _compute_non_silent_segments(
    silent_segments: list[tuple[float, float]],
    total_duration: float,
) -> list[tuple[float, float]]:

    if not silent_segments:
        return [(0.0, total_duration)]

    silent_segments = sorted(silent_segments, key=lambda x: x[0])

    non_silent: list[tuple[float, float]] = []
    prev_end = 0.0

    for sil_start, sil_end in silent_segments:
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

    if progress_callback:
        progress_callback(10)

    silent_segments = detect_silent_segments(
        input_path, threshold_db, min_duration
    )

    if progress_callback:
        progress_callback(30)

    if not silent_segments:
        logger.info("No silence detected — copying original")
        import shutil
        shutil.copy2(input_path, output_path)
        if progress_callback:
            progress_callback(100)
        return

    total_duration = get_video_duration(input_path)
    non_silent = _compute_non_silent_segments(silent_segments, total_duration)

    if not non_silent:
        logger.warning("No audible segments found — copying original")
        import shutil
        shutil.copy2(input_path, output_path)
        if progress_callback:
            progress_callback(100)
        return

    if progress_callback:
        progress_callback(50)

    n = len(non_silent)
    filter_parts: list[str] = []
    concat_inputs = ""

    for i, (start, end) in enumerate(non_silent):
        duration = max(0.0, end - start)

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

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg silence removal failed: {result.stderr[-500:]}"
        )

    if progress_callback:
        progress_callback(100)

    logger.info(
        "Silence removal complete — removed %d silent segments",
        len(silent_segments),
    )