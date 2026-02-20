import asyncio
import logging
import shutil
from datetime import datetime
from typing import Any, Callable, Coroutine

from app.utils.files import (
    get_metadata,
    get_video_path,
    update_metadata_processing_status,
    update_processing_progress,
)

logger = logging.getLogger(__name__)


class ProcessingContext:
    def __init__(self, video_id: str):
        self.video_id = video_id
        self.metadata = get_metadata(video_id)
        self.input_path = get_video_path(
            video_id, self.metadata["extension"], processed=False
        )
        self.output_path = get_video_path(
            video_id, self.metadata["extension"], processed=True
        )
        self.start_time: datetime | None = None

    def update_progress(
        self,
        progress: float,
        current_step: str = "",
        total_steps: int = 0,
        current_step_progress: float = 0,
    ) -> None:
        update_processing_progress(
            self.video_id,
            progress,
            current_step,
            total_steps,
            current_step_progress,
        )

    def update_status(self, status: str, processed: bool = False) -> None:
        update_metadata_processing_status(self.video_id, status, processed)

    async def __aenter__(self):
        self.start_time = datetime.now()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.update_status("processing")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = datetime.now() - self.start_time

        if exc_type is None:
            self.update_progress(100)
            self.update_status("completed", processed=True)
            logger.info(
                "Video %s completed in %.2f seconds",
                self.video_id,
                duration.total_seconds(),
            )
        else:
            self.update_status("error")
            logger.error(
                "Video %s failed after %.2f seconds: %s",
                self.video_id,
                duration.total_seconds(),
                exc_val,
            )
            return False


async def process_video(
    video_id: str,
    processor: Callable[[ProcessingContext], Coroutine[Any, Any, None]],
) -> None:
    async with ProcessingContext(video_id) as context:
        await processor(context)


async def video_processor(context: ProcessingContext) -> None:
    options = context.metadata.get("processing_options", {})

    steps: list[tuple[str, str]] = []

    if options.get("edit_operations"):
        steps.append(("Natural Language Editing", "nl_edit"))
    if options.get("remove_silence"):
        steps.append(("Silence Removal", "silence_removal"))
    if options.get("auto_crop_face"):
        steps.append(("Face Auto-Crop", "face_crop"))

    if not steps:
        shutil.copy2(context.input_path, context.output_path)
        return

    total_steps = len(steps)
    current_input = context.input_path
    temp_files = []

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
            weight = 100 / total_steps

            def progress_cb(sub_progress: float):
                overall = base_progress + (sub_progress / 100) * weight
                context.update_progress(
                    overall,
                    current_step=step_name,
                    total_steps=total_steps,
                    current_step_progress=sub_progress,
                )

            if step_key == "nl_edit":
                from app.utils.ffmpeg_ops import apply_operations

                await asyncio.to_thread(
                    apply_operations,
                    current_input,
                    step_output,
                    options["edit_operations"],
                    progress_cb,
                )

            elif step_key == "silence_removal":
                from app.utils.silence import remove_silence

                await asyncio.to_thread(
                    remove_silence,
                    current_input,
                    step_output,
                    progress_cb,
                )

            elif step_key == "face_crop":
                from app.utils.face_crop import auto_crop_face

                await asyncio.to_thread(
                    auto_crop_face,
                    current_input,
                    step_output,
                    progress_cb,
                )

            current_input = step_output

    finally:
        for tf in temp_files:
            if tf.exists():
                try:
                    tf.unlink()
                except OSError:
                    logger.warning("Failed to clean up temp file: %s", tf)