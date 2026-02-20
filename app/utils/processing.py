import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine

from app.core.settings import settings
from app.utils.files import (
    get_metadata,
    update_metadata_processing_status,
    update_processing_progress,
    get_video_path,
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

    def update_progress(self, progress: float) -> None:
        update_processing_progress(self.video_id, progress)

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
            self.update_status("completed", processed=True)
            self.update_progress(100)
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


async def stub_processor(context: ProcessingContext) -> None:
    total_steps = 5

    for step in range(total_steps):
        progress = ((step + 1) / total_steps) * 100
        context.update_progress(progress)
        await asyncio.sleep(1)

    # For stub: simply copy input → output
    context.output_path.write_bytes(context.input_path.read_bytes())