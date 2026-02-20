import subprocess
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

def get_video_duration(input_path: Path) -> float:
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
    except ValueError:
        raise RuntimeError("Failed to parse video duration")


def apply_operations(
    input_path: Path,
    output_path: Path,
    operations: list[dict[str, Any]],
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:

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
                else input_path.parent / f"_temp_{i}_{input_path.stem}{input_path.suffix}"
            )

            if not is_last:
                temp_files.append(current_output)

            if progress_callback:
                progress_callback((i / total_ops) * 100)

            if op_type == "trim_start":
                _trim_start(current_input, current_output, op["seconds"])

            elif op_type == "trim_end":
                _trim_end(current_input, current_output, op["seconds"])

            elif op_type == "speed":
                _change_speed(current_input, current_output, op["factor"])

            elif op_type == "fade_out":
                _fade_out(current_input, current_output, op["seconds"])

            else:
                raise ValueError(f"Unsupported operation type: {op_type}")

            current_input = current_output

        if progress_callback:
            progress_callback(100)

    finally:
        for tf in temp_files:
            if tf.exists():
                try:
                    tf.unlink()
                except OSError:
                    pass


def _run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-500:])


def _trim_start(input_path: Path, output_path: Path, seconds: float) -> None:
    _run_ffmpeg([
        "-i", str(input_path),
        "-ss", str(seconds),
        "-c", "copy",
        str(output_path),
    ])


def _trim_end(input_path: Path, output_path: Path, seconds: float) -> None:
    duration = get_video_duration(input_path)
    end_time = max(0, duration - seconds)

    _run_ffmpeg([
        "-i", str(input_path),
        "-t", str(end_time),
        "-c", "copy",
        str(output_path),
    ])


def _change_speed(input_path: Path, output_path: Path, factor: float) -> None:
    video_filter = f"setpts={1 / factor}*PTS"

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
    duration = get_video_duration(input_path)
    fade_start = max(0, duration - seconds)

    _run_ffmpeg([
        "-i", str(input_path),
        "-vf", f"fade=t=out:st={fade_start}:d={seconds}",
        "-af", f"afade=t=out:st={fade_start}:d={seconds}",
        str(output_path),
    ])