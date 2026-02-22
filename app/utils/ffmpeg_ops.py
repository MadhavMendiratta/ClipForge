"""FFmpeg operation utilities for applying video editing operations."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def get_video_duration(input_path: Path) -> float:
    """
    Get the duration of a video file in seconds using ffprobe.

    Args:
        input_path: Path to the video file.

    Returns:
        Duration in seconds.

    Raises:
        RuntimeError: If ffprobe fails to determine the duration.
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")
    try:
        return float(result.stdout.strip())
    except ValueError as e:
        raise RuntimeError(f"Could not parse duration: {result.stdout.strip()}") from e


def apply_operations(
    input_path: Path,
    output_path: Path,
    operations: list[dict[str, Any]],
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    """
    Apply a sequence of editing operations to a video file using ffmpeg.

    Args:
        input_path: Path to the source video.
        output_path: Path for the output video.
        operations: List of operation dicts (type + params).
        progress_callback: Optional callback receiving progress percentage (0-100).
    """
    if not operations:
        shutil.copy2(input_path, output_path)
        if progress_callback:
            progress_callback(100)
        return

    total_ops = len(operations)
    current_input = input_path
    temp_files: list[Path] = []

    try:
        for i, op in enumerate(operations):
            op_type = op["type"]
            is_last = i == total_ops - 1
            current_output = (
                output_path
                if is_last
                else input_path.parent / f"_nltemp_{i}_{input_path.stem}{input_path.suffix}"
            )

            if not is_last:
                temp_files.append(current_output)

            if progress_callback:
                progress_callback((i / total_ops) * 100)

            logger.info("Applying operation %d/%d: %s", i + 1, total_ops, op_type)

            if op_type == "trim_start":
                _trim_start(current_input, current_output, op["seconds"])
            elif op_type == "trim_end":
                _trim_end(current_input, current_output, op["seconds"])
            elif op_type == "speed":
                _change_speed(current_input, current_output, op["factor"])
            elif op_type == "fade_out":
                _fade_out(current_input, current_output, op["seconds"])
            else:
                logger.warning("Unknown operation type: %s, skipping", op_type)
                if not is_last:
                    shutil.copy2(current_input, current_output)

            current_input = current_output

        if progress_callback:
            progress_callback(100)

    finally:
        for tf in temp_files:
            if tf.exists():
                try:
                    tf.unlink()
                except OSError:
                    logger.warning("Failed to clean up temp file: %s", tf)


def _run_ffmpeg(args: list[str]) -> None:
    """Run an ffmpeg command and raise on failure."""
    cmd = ["ffmpeg", "-y"] + args
    logger.debug("Running ffmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")


def _trim_start(input_path: Path, output_path: Path, seconds: float) -> None:
    """Trim the beginning of the video."""
    _run_ffmpeg([
        "-i", str(input_path),
        "-ss", str(seconds),
        "-c", "copy",
        str(output_path),
    ])


def _trim_end(input_path: Path, output_path: Path, seconds: float) -> None:
    """Trim the end of the video."""
    duration = get_video_duration(input_path)
    end_time = max(0, duration - seconds)
    _run_ffmpeg([
        "-i", str(input_path),
        "-t", str(end_time),
        "-c", "copy",
        str(output_path),
    ])


def _change_speed(input_path: Path, output_path: Path, factor: float) -> None:
    """Change the playback speed of the video."""
    video_filter = f"setpts={1 / factor}*PTS"

    # atempo only supports values between 0.5 and 100.0; chain filters for extremes
    audio_parts: list[str] = []
    remaining = factor
    while remaining > 2.0:
        audio_parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        audio_parts.append("atempo=0.5")
        remaining /= 0.5
    audio_parts.append(f"atempo={remaining}")
    audio_filter = ",".join(audio_parts)

    _run_ffmpeg([
        "-i", str(input_path),
        "-filter:v", video_filter,
        "-filter:a", audio_filter,
        str(output_path),
    ])


def _fade_out(input_path: Path, output_path: Path, seconds: float) -> None:
    """Add fade-out effect to the end of the video."""
    duration = get_video_duration(input_path)
    fade_start = max(0, duration - seconds)
    _run_ffmpeg([
        "-i", str(input_path),
        "-vf", f"fade=t=out:st={fade_start}:d={seconds}",
        "-af", f"afade=t=out:st={fade_start}:d={seconds}",
        str(output_path),
    ])
