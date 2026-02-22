"""Video processing utilities for the application."""

import asyncio
import logging
import shutil
from datetime import datetime
from typing import Any, Callable, Coroutine

from app.core.settings import settings

from .files import (
    get_metadata,
    update_metadata_processing_status,
    update_processing_progress,
)

logger = logging.getLogger(__name__)


class ProcessingContext:
    """Context manager for video processing operations."""

    def __init__(self, video_id: str):
        self.video_id = video_id
        self.metadata = get_metadata(video_id)
        self.input_path = (
            settings.upload_dir / f"{video_id}.{self.metadata['extension']}"
        )
        self.output_path = (
            settings.processed_dir
            / f"{settings.processed_prefix}{video_id}.{self.metadata['extension']}"
        )
        self.start_time = None

    def update_progress(
        self,
        progress: float,
        current_step: str = "",
        total_steps: int = 0,
        current_step_progress: float = 0,
    ) -> None:
        """Update processing progress."""
        update_processing_progress(
            self.video_id, progress, current_step, total_steps, current_step_progress
        )
        logger.debug(f"Video {self.video_id} processing progress: {progress}%")

    def update_status(self, status: str, processed: bool = False) -> None:
        """Update processing status."""
        update_metadata_processing_status(self.video_id, status, processed)
        logger.info(f"Video {self.video_id} status updated to: {status}")

    async def __aenter__(self):
        """Set up processing context."""
        logger.info(f"Starting processing for video {self.video_id}")
        self.start_time = datetime.now()
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        # Update status to processing
        self.update_status("processing")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up processing context."""
        duration = datetime.now() - self.start_time

        if exc_type is None:
            # Processing completed successfully
            self.update_status("completed", processed=True)
            self.update_progress(100)
            logger.info(
                f"Video {self.video_id} processing completed successfully "
                f"in {duration.total_seconds():.2f} seconds"
            )
        else:
            # Processing failed
            logger.error(
                f"Processing failed for video {self.video_id} after "
                f"{duration.total_seconds():.2f} seconds: {exc_val}"
            )
            self.update_status("error")
            return False  # Re-raise the exception

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


async def process_video(
    video_id: str, processor: Callable[[ProcessingContext], Coroutine[Any, Any, None]]
) -> None:
    """
    Process a video using the provided processor function.

    Args:
        video_id: UUID of the video to process
        processor: Async function that implements the video processing logic
    """
    logger.info(f"Starting background task for video {video_id}")
    try:
        async with ProcessingContext(video_id) as context:
            await processor(context)
        logger.info(f"Background task completed for video {video_id}")
    except Exception as e:
        logger.error(f"Background task failed for video {video_id}: {str(e)}")
        raise


# Example stub processing function
async def stub_processor(context: ProcessingContext) -> None:
    """
    Stub processor that simulates video processing.
    Replace this with actual video processing logic.
    """
    total_steps = 3

    try:
        # Simulate processing steps
        for step in range(total_steps):
            step_name = f"Processing step {step + 1}"
            logger.debug(f"Video {context.video_id}: Starting {step_name}")

            # Simulate step progress
            for progress in range(0, 101, 10):
                context.update_progress(
                    progress=((step * 100 + progress) / total_steps),
                    current_step=step_name,
                    total_steps=total_steps,
                    current_step_progress=progress,
                )
                await asyncio.sleep(0.5)  # Simulate processing time

            logger.debug(f"Video {context.video_id}: Completed {step_name}")

    except Exception as e:
        logger.error(f"Stub processor failed for video {context.video_id}: {str(e)}")
        raise


async def video_processor(context: ProcessingContext) -> None:
    """
    Main video processor that runs the configured pipeline steps.

    Reads processing_options from metadata and executes the appropriate
    pipeline steps in order:
        1. Natural language edit operations (trim, speed, fade)
        2. Silence removal
        3. Talking-head face auto-crop

    If no processing options are set, the original file is copied as-is.
    """
    options = context.metadata.get("processing_options", {})

    # Build the ordered pipeline
    steps: list[tuple[str, Any]] = []

    if options.get("edit_operations"):
        steps.append(("Natural Language Editing", "nl_edit"))
    if options.get("remove_silence"):
        steps.append(("Silence Removal", "silence_removal"))
    if options.get("auto_crop_face"):
        steps.append(("Face Auto-Crop", "face_crop"))

    if not steps:
        # No processing requested — copy original to processed
        logger.info("No processing options set for %s, copying original", context.video_id)
        context.output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(context.input_path, context.output_path)
        return

    total_steps = len(steps)
    current_input = context.input_path
    temp_files: list = []

    try:
        for i, (step_name, step_key) in enumerate(steps):
            is_last = i == total_steps - 1
            step_output = (
                context.output_path
                if is_last
                else context.input_path.parent
                / f"_pipeline_{i}_{context.video_id}{context.input_path.suffix}"
            )

            if not is_last:
                temp_files.append(step_output)

            base_progress = (i / total_steps) * 100
            step_weight = 100 / total_steps

            def _make_progress_cb(
                base: float, weight: float, name: str, total: int
            ) -> Callable[[float], None]:
                def cb(sub_progress: float) -> None:
                    overall = base + (sub_progress / 100) * weight
                    context.update_progress(overall, name, total, sub_progress)

                return cb

            progress_cb = _make_progress_cb(base_progress, step_weight, step_name, total_steps)

            logger.info(
                "Video %s: Starting step %d/%d — %s",
                context.video_id,
                i + 1,
                total_steps,
                step_name,
            )

            if step_key == "nl_edit":
                from app.utils.ffmpeg_ops import apply_operations

                edit_ops = options["edit_operations"]
                await asyncio.to_thread(
                    apply_operations, current_input, step_output, edit_ops, progress_cb
                )

            elif step_key == "silence_removal":
                from app.utils.silence import remove_silence

                await asyncio.to_thread(
                    remove_silence, current_input, step_output, progress_cb
                )

            elif step_key == "face_crop":
                from app.utils.face_crop import auto_crop_face

                await asyncio.to_thread(
                    auto_crop_face, current_input, step_output, progress_cb
                )

            # Move to next input
            current_input = step_output

            logger.info(
                "Video %s: Completed step %d/%d — %s",
                context.video_id,
                i + 1,
                total_steps,
                step_name,
            )

    finally:
        # Clean up intermediate pipeline files
        for tf in temp_files:
            try:
                if tf.exists():
                    tf.unlink()
            except OSError:
                logger.warning("Failed to clean up temp file: %s", tf)
