"""Talking-head auto-crop using MediaPipe face detection."""

import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional

import cv2
import mediapipe as mp
import numpy as np

logger = logging.getLogger(__name__)

# Target aspect ratio for vertical video
TARGET_ASPECT_W = 9
TARGET_ASPECT_H = 16

# Number of frames to sample for face position estimation
SAMPLE_FRAME_COUNT = 60

# Smoothing window for face center positions
SMOOTHING_WINDOW = 5


def _sample_face_positions(
    input_path: Path,
    sample_count: int = SAMPLE_FRAME_COUNT,
) -> list[tuple[float, float, float, float]]:
    """
    Sample frames from the video and detect face bounding boxes.

    Args:
        input_path: Path to the video file.
        sample_count: Number of frames to sample.

    Returns:
        List of (center_x, center_y, width, height) in normalized coords [0, 1].
    """
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        raise RuntimeError(f"Cannot determine frame count: {input_path}")

    # Evenly sample frame indices
    indices = np.linspace(0, total_frames - 1, min(sample_count, total_frames), dtype=int)

    face_positions: list[tuple[float, float, float, float]] = []

    mp_face = mp.solutions.face_detection
    with mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_detection.process(rgb)

            if results.detections:
                # Use the first (most confident) detection
                det = results.detections[0]
                bb = det.location_data.relative_bounding_box
                cx = bb.xmin + bb.width / 2
                cy = bb.ymin + bb.height / 2
                face_positions.append((cx, cy, bb.width, bb.height))

    cap.release()

    logger.info(
        "Detected faces in %d / %d sampled frames",
        len(face_positions),
        len(indices),
    )
    return face_positions


def _compute_crop_region(
    face_positions: list[tuple[float, float, float, float]],
    video_width: int,
    video_height: int,
) -> tuple[int, int, int, int]:
    """
    Compute a stable 9:16 crop region centered on the average face position.

    Args:
        face_positions: List of (cx, cy, w, h) in normalized coords.
        video_width: Width of the source video in pixels.
        video_height: Height of the source video in pixels.

    Returns:
        (crop_x, crop_y, crop_w, crop_h) in pixels.
    """
    if not face_positions:
        # Default: center crop
        avg_cx = 0.5
        avg_cy = 0.5
    else:
        # Smoothed average face center
        centers_x = [p[0] for p in face_positions]
        centers_y = [p[1] for p in face_positions]
        avg_cx = float(np.mean(centers_x))
        avg_cy = float(np.mean(centers_y))

    # Target 9:16 crop
    # Use full height, compute width from aspect ratio
    crop_h = video_height
    crop_w = int(crop_h * TARGET_ASPECT_W / TARGET_ASPECT_H)

    # If computed crop width exceeds video width, scale down
    if crop_w > video_width:
        crop_w = video_width
        crop_h = int(crop_w * TARGET_ASPECT_H / TARGET_ASPECT_W)

    # Ensure even dimensions (required by many codecs)
    crop_w = crop_w - (crop_w % 2)
    crop_h = crop_h - (crop_h % 2)

    # Center the crop on the face
    crop_x = int(avg_cx * video_width - crop_w / 2)
    crop_y = int(avg_cy * video_height - crop_h / 2)

    # Clamp to video bounds
    crop_x = max(0, min(crop_x, video_width - crop_w))
    crop_y = max(0, min(crop_y, video_height - crop_h))

    return crop_x, crop_y, crop_w, crop_h


def auto_crop_face(
    input_path: Path,
    output_path: Path,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    """
    Auto-crop a video to 9:16 vertical format centered on detected face.

    Steps:
        1. Sample frames and detect face positions with MediaPipe.
        2. Compute a stable averaged crop region.
        3. Apply the crop using ffmpeg.

    Args:
        input_path: Path to the input video.
        output_path: Path for the output video.
        progress_callback: Optional callback receiving progress percentage (0-100).
    """
    if progress_callback:
        progress_callback(5)

    # Get video dimensions
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    logger.info("Input video dimensions: %dx%d", video_width, video_height)

    if progress_callback:
        progress_callback(10)

    # Step 1: Detect face positions across sampled frames
    face_positions = _sample_face_positions(input_path)

    if progress_callback:
        progress_callback(50)

    if not face_positions:
        logger.warning("No faces detected — using center crop")

    # Step 2: Compute crop region
    crop_x, crop_y, crop_w, crop_h = _compute_crop_region(
        face_positions, video_width, video_height
    )

    logger.info(
        "Crop region: x=%d, y=%d, w=%d, h=%d", crop_x, crop_y, crop_w, crop_h
    )

    if progress_callback:
        progress_callback(60)

    # Step 3: Apply crop with ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}",
        "-c:a", "copy",
        str(output_path),
    ]

    logger.debug("Running face crop ffmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg face crop failed: {result.stderr[-500:]}")

    if progress_callback:
        progress_callback(100)

    logger.info("Face auto-crop complete: %dx%d output", crop_w, crop_h)
