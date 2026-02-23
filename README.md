# ClipForge

A self-hosted video processing API and web interface built with FastAPI. StreamForge provides automated video editing capabilities including face-aware cropping, silence removal, and natural language editing via LLM integration. Videos are uploaded through a browser UI or API, processed asynchronously on the server, and made available for streaming, download, or sharing via tokenized links.

## Features

- **Video Upload and Processing Pipeline** -- Upload videos through a web UI or REST API. Processing runs asynchronously in the background with real-time progress tracking via Server-Sent Events (SSE).
- **Face Auto-Crop** -- Automatically crop landscape video to 9:16 vertical format centered on detected faces using MediaPipe face detection. Samples frames across the video to compute a stable, averaged crop region.
- **Silence Removal** -- Detect and remove silent segments from video using FFmpeg's `silencedetect` filter. Non-silent segments are extracted and concatenated into a clean output.
- **Natural Language Editing** -- Describe edits in plain English (e.g., "trim the first 10 seconds and speed up 1.5x"). Instructions are parsed by an OpenAI LLM into structured operations (trim, speed change, fade-out) and applied via FFmpeg.
- **Processing Presets** -- Save and reuse named combinations of processing options (edit instructions, silence removal, face crop) as presets stored in SQLite.
- **Shareable Video Links** -- Generate tokenized share links with optional expiration time and view count limits. Shared videos are streamed through a public endpoint without authentication.
- **System Health Dashboard** -- Monitor FFmpeg availability, disk usage, and database status through a detailed health check endpoint and web page.
- **Video Streaming** -- Stream original and processed videos with chunked transfer encoding. Supports MP4, AVI, MOV, and MKV formats.

## Tech Stack

| Layer          | Technology                                                   |
|----------------|--------------------------------------------------------------|
| Backend        | Python, FastAPI, Uvicorn                                     |
| Templating     | Jinja2, Tailwind CSS (via CDN)                               |
| Video Processing | FFmpeg, OpenCV, MediaPipe (Tasks API)                      |
| LLM Integration | OpenAI API (GPT-4o)                                        |
| Database       | SQLite (WAL mode) -- presets and share tokens                |
| Real-time      | Server-Sent Events (SSE) via `sse-starlette`                 |
| Validation     | Pydantic, Pydantic Settings                                  |

## Project Structure

```
clip-forge/
├── main.py                     # FastAPI application entry point, router registration
├── app/
│   ├── core/
│   │   └── settings.py         # Pydantic-based application settings
│   ├── models/
│   │   └── database.py         # SQLite layer: presets CRUD, share token CRUD
│   ├── routes/
│   │   ├── dashboard.py        # HTML page routes (upload, video, videos, health, presets)
│   │   ├── upload.py           # POST /api/upload -- file upload + background processing
│   │   ├── video.py            # Video streaming, metadata, SSE status, video listing
│   │   ├── presets.py          # CRUD endpoints for processing presets
│   │   ├── share.py            # Share link creation and public video streaming
│   │   └── health.py           # Health check endpoints (simple + detailed)
│   ├── templates/              # Jinja2 HTML templates for the web UI
│   │   ├── base.html
│   │   ├── upload.html
│   │   ├── video.html
│   │   ├── videos.html
│   │   ├── presets.html
│   │   ├── health.html
│   │   └── dashboard.html
│   └── utils/
│       ├── face_crop.py        # MediaPipe face detection + FFmpeg 9:16 crop
│       ├── ffmpeg_ops.py       # FFmpeg operations: trim, speed, fade-out
│       ├── silence.py          # Silence detection and removal via FFmpeg
│       ├── llm.py              # OpenAI integration for NL edit parsing
│       ├── files.py            # File I/O, metadata management, video path resolution
│       └── processing.py       # Async processing pipeline orchestration
├── static/
│   └── app.js                  # Client-side JS (sidebar, toasts, clipboard)
├── data/
│   └── blaze_face_short_range.tflite  # MediaPipe face detection model
├── uploads/                    # Uploaded video files + JSON metadata
├── processed/                  # Processed output videos
├── requirements.txt
├── sample.env
├── setup.sh
├── start.sh
└── pytest.ini
```

## Installation and Setup

### Prerequisites

- Python 3.10+
- FFmpeg (must be available on `PATH`)
- An OpenAI API key (required only for the natural language editing feature)

### Clone

```bash
git clone https://github.com/MadhavMendiratta/ClipForge.git
cd ClipForge
```

### Environment Variables

Copy the sample environment file and edit it:

```bash
cp sample.env .env
```

| Variable               | Description                              | Default            |
|------------------------|------------------------------------------|--------------------|
| `HOST`                 | Server bind address                      | `0.0.0.0`         |
| `PORT`                 | Server port                              | `8000`            |
| `DEBUG`                | Enable debug mode and auto-reload        | `True`            |
| `MAX_UPLOAD_SIZE`      | Maximum upload size in bytes             | `524288000` (500MB)|
| `ALLOWED_EXTENSIONS`   | Comma-separated allowed video formats    | `mp4, avi, mov, mkv` |
| `UPLOAD_DIR`           | Directory for uploaded files             | `uploads`         |
| `PROCESSED_DIR`        | Directory for processed output           | `processed`       |
| `OPENAI_API_KEY`       | OpenAI API key for NL editing            | --                |
| `OPENAI_MODEL`         | OpenAI model name                        | `gpt-4o`          |
| `VIDEO_DATABASE_PATH`  | SQLite database file path                | `data/app.db`     |

### Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create the required directories:

```bash
mkdir -p static uploads processed data
```

The face detection model (`data/blaze_face_short_range.tflite`) is required for the auto-crop feature. If it is not present, download it:

```bash
curl -L -o data/blaze_face_short_range.tflite \
  "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
```

## Running the Project

```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The application will be available at `http://localhost:8000`.

Alternatively, use the provided scripts:

```bash
chmod +x setup.sh start.sh
./setup.sh    # One-time setup
./start.sh    # Start the server
```

## API Endpoints

### Upload

| Method | Path           | Description                                      |
|--------|----------------|--------------------------------------------------|
| POST   | `/api/upload`  | Upload a video file. Accepts multipart form with fields: `video` (file), `edit_text` (string), `remove_silence` (bool), `auto_crop_face` (bool), `preset_id` (string). Returns video ID and starts background processing. |

### Video

| Method | Path                               | Description                              |
|--------|------------------------------------|------------------------------------------|
| GET    | `/api/video/{video_id}`            | Stream a video. Query param `type`: `original` or `processed`. |
| GET    | `/api/video/{video_id}/metadata`   | Get video metadata JSON.                 |
| GET    | `/api/video/{video_id}/status/stream` | SSE stream of processing status updates. |
| GET    | `/api/videos/list`                 | List all videos with metadata.           |

### Presets

| Method | Path                         | Description                    |
|--------|------------------------------|--------------------------------|
| GET    | `/api/presets`               | List all presets.              |
| POST   | `/api/presets`               | Create a new preset.           |
| GET    | `/api/presets/{preset_id}`   | Get a preset by ID.            |

### Share

| Method | Path                              | Description                                  |
|--------|-----------------------------------|----------------------------------------------|
| POST   | `/api/video/{video_id}/share`     | Create a share link. Body: `expires_in_hours`, `max_views`. |
| GET    | `/public/video/{token}`           | Stream a shared video via token. Query param `type`: `original` or `processed`. |

### Health

| Method | Path                    | Description                                      |
|--------|-------------------------|--------------------------------------------------|
| GET    | `/api/health`           | Simple health check (`{"status": "healthy"}`).   |
| GET    | `/api/health/detailed`  | Detailed check: FFmpeg, disk, database status.   |

### Web Pages

| Path        | Page                          |
|-------------|-------------------------------|
| `/`         | Upload page (root redirect)   |
| `/upload`   | Video upload form              |
| `/video/{id}` | Video processing result page |
| `/videos`   | My Videos listing              |
| `/presets`  | Presets management             |
| `/health`   | System health dashboard        |

Full interactive API documentation is available at `/docs` (Swagger UI) and `/redoc`.

## Usage

1. Open `http://localhost:8000` in a browser.
2. Upload a video file using the upload form.
3. Select processing options: auto-crop to face, remove silence, or enter natural language edit instructions.
4. Optionally apply a saved preset instead of selecting options manually.
5. After upload, the video processing page shows real-time progress via SSE.
6. Once processing completes, both the original and processed videos are available for playback and download.
7. Generate a shareable link for the processed video with optional expiry and view limits.

## Running Tests

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Future Improvements

- Batch processing for multiple video uploads in a single request.
- Additional FFmpeg operations: audio normalization, watermarking, resolution scaling.
- Persistent job queue (Redis or PostgreSQL) to replace in-process background tasks and support horizontal scaling.
- User authentication and per-user video isolation.
- Thumbnail generation and video preview on the listing page.
- WebSocket-based progress updates as an alternative to SSE.
- Configurable silence detection thresholds via the upload form and presets.
- Support for custom crop aspect ratios beyond 9:16.

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes with clear messages.
4. Push to the branch and open a pull request.
5. Ensure all existing tests pass before submitting.
