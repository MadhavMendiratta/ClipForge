"""Talking-head auto-crop using MediaPipe face detection."""

import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional

import cv2
import mediapipe as mp
import numpy as np

logger = logging.getLogger(__name__)

TARGET_ASPECT_W = 9
TARGET_ASPECT_H = 16
SAMPLE_FRAME_COUNT = 60


def _sample_face_positions(
    input_path: Path,
    sample_count: int = SAMPLE_FRAME_COUNT,
) -> list[tuple[float, float, float, float]]:

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return []

    indices = np.linspace(
        0,
        total_frames - 1,
        min(sample_count, total_frames),
        dtype=int,
    )

    face_positions: list[tuple[float, float, float, float]] = []

    mp_face = mp.solutions.face_detection
    try:
        with mp_face.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5,
        ) as face_detection:

            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ret, frame = cap.read()
                if not ret:
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_detection.process(rgb)

                if results.detections:
                    det = results.detections[0]
                    bb = det.location_data.relative_bounding_box

                    cx = bb.xmin + bb.width / 2
                    cy = bb.ymin + bb.height / 2

                    # Clamp normalized coords
                    cx = float(np.clip(cx, 0.0, 1.0))
                    cy = float(np.clip(cy, 0.0, 1.0))

                    face_positions.append((cx, cy, bb.width, bb.height))

    finally:
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

    if video_width <= 0 or video_height <= 0:
        raise RuntimeError("Invalid video dimensions")

    if not face_positions:
        avg_cx = 0.5
        avg_cy = 0.5
    else:
        centers_x = [p[0] for p in face_positions]
        centers_y = [p[1] for p in face_positions]

        avg_cx = float(np.mean(centers_x))
        avg_cy = float(np.mean(centers_y))

        avg_cx = float(np.clip(avg_cx, 0.0, 1.0))
        avg_cy = float(np.clip(avg_cy, 0.0, 1.0))

    crop_h = video_height
    crop_w = int(crop_h * TARGET_ASPECT_W / TARGET_ASPECT_H)

    if crop_w > video_width:
        crop_w = video_width
        crop_h = int(crop_w * TARGET_ASPECT_H / TARGET_ASPECT_W)

    crop_w -= crop_w % 2
    crop_h -= crop_h % 2

    crop_x = int(avg_cx * video_width - crop_w / 2)
    crop_y = int(avg_cy * video_height - crop_h / 2)

    crop_x = max(0, min(crop_x, video_width - crop_w))
    crop_y = max(0, min(crop_y, video_height - crop_h))

    return crop_x, crop_y, crop_w, crop_h


def auto_crop_face(
    input_path: Path,
    output_path: Path,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:

    if progress_callback:
        progress_callback(5)

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if progress_callback:
        progress_callback(10)

    face_positions = _sample_face_positions(input_path)

    if progress_callback:
        progress_callback(50)

    crop_x, crop_y, crop_w, crop_h = _compute_crop_region(
        face_positions,
        video_width,
        video_height,
    )

    if progress_callback:
        progress_callback(60)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}",
        "-c:a",
        "copy",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg face crop failed: {result.stderr[-500:]}"
        )

    if progress_callback:
        progress_callback(100)

    logger.info(
        "Face auto-crop complete — output size: %dx%d",
        crop_w,
        crop_h,
    )