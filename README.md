# Video & Audio Transcription (YouTube & Local Media)

Minimalist web application for transcribing **YouTube** videos from a URL or video ID, as well as **local video and audio files** using AI powered by **Whisper (`faster-whisper`)**. Features interactive timestamp-synced playback and multi-format export.

## Features

- **Minimalist Design**: Clean zinc/slate aesthetic with automatic system theme detection and a persistent Light/Dark toggle.
- **Dual Media Input**:
  - **YouTube**: Supports standard URLs (`youtube.com/watch?v=...`), shortened links (`youtu.be/...`), Shorts (`youtube.com/shorts/...`), Live/embedded links, and raw video IDs. Defaults to English or manual subtitle tracks when available.
  - **Local Files**: Drag & drop any media file, browse from disk, or specify a local disk path directly (MP4, MKV, WebM, AVI, MOV, MP3, WAV, M4A, FLAC, OPUS, etc.).
- **Local Whisper Engine (`faster-whisper`)**:
  - CPU-accelerated inference with INT8 quantization.
  - Selectable models: `base` (recommended), `tiny` (ultra-fast), `small` (higher accuracy), and `medium`.
  - Automatic language detection or explicit language selection (English, Spanish, French, German, Italian, Portuguese, Dutch, Polish, Russian, Turkish, Ukrainian, Chinese, Japanese).
  - Voice Activity Detection (VAD) filter to skip silent segments.
- **Synced Local Player**:
  - Dedicated video or audio player depending on the media stream, highlighting the active transcript segment in real time and jumping to any timestamp on click.
- **Dual Reading Modes & Keyboard Accessibility**:
  - *Timestamps View*: Segment list with clickable timecodes and one-click copy per segment.
  - *Continuous Text*: Clean flowing paragraphs optimized for reading or feeding into LLMs.
  - Native modal history drawer and full keyboard navigation across tabs and menus.
- **Real-Time Search**: Instant keyword filtering and highlighting with a live match counter.
- **Multi-Format Export**:
  - `.txt` (Plain text or with timestamps)
  - `.pdf` (Formatted document with metadata and pagination)
  - `.srt` (SubRip subtitles)
  - `.vtt` (WebVTT captions)
  - `.json` (Structured JSON payload)
  - `.csv` (Spreadsheet-ready table)
  - `.md` (Markdown with structured metadata)
- **Quick Copy & Local History**: One-click clipboard copy and browser-persisted recent transcription history.

## Requirements

- Python 3.10 or higher.
- `ffmpeg` and `ffprobe` installed and available in `PATH` (required for local media metadata, thumbnails, and Whisper decoding).

## Installation & Usage

1. Run the launcher script:
   ```bash
   ./run.sh
   ```

   Or set it up manually:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```

2. Open your browser at **[http://127.0.0.1:8001](http://127.0.0.1:8001)** (or launch it via **Tools Hub**).

## Configuration

| Environment Variable | Default | Description |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Bind host (`0.0.0.0` to expose on LAN). |
| `PORT` | `8001` | HTTP server port. |
| `RELOAD` | `0` | Set to `1` to enable Uvicorn auto-reload during development. |
| `TRANSCRIPT_PYTHON` | *(auto-detected)* | Explicit Python interpreter path used by `run.sh`. |

### Health Check

`GET /api/health` returns service readiness and capability flags:

```json
{
  "status": "ok",
  "ffmpeg": true,
  "whisper_available": true
}
```

## Running Tests

Install development/test dependencies and run `pytest`:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -v tests/
```
