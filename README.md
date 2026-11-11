# Video & Audio Transcription (YouTube & Local Media)

Minimalist web application for transcribing **YouTube** videos from a URL or video ID, as well as **local video and audio files** using AI powered by **Whisper (`faster-whisper`)**. Features interactive timestamp-synced playback and multi-format export.

## ✨ Features

- **Minimalist Design**: Clean zinc/slate aesthetic with automatic and manual **Light Mode** and **Dark Mode** support.
- **Dual Media Input**:
  - **YouTube**: Supports standard URLs (`youtube.com/watch?v=...`), shortened links (`youtu.be/...`), Shorts (`youtube.com/shorts/...`), embedded links, and raw video IDs.
  - **Local Files**: Drag & Drop any media file or specify a local disk path directly (MP4, MKV, WebM, AVI, MOV, MP3, WAV, M4A, FLAC, etc.).
- **Local Whisper Engine (`faster-whisper`)**:
  - CPU-accelerated inference with INT8 quantization.
  - Selectable models: `base` (recommended), `tiny` (ultra-fast), `small` (high accuracy), and `medium`.
  - Automatic language detection or manual selection (English, Spanish, French, German, Italian, Portuguese, etc.).
  - Voice Activity Detection (VAD) filter to skip silent segments.
- **Synced Local Player**:
  - Built-in media player for local files that jumps to the exact second when clicking any timestamp.
- **Dual Reading Modes**:
  - *Timestamps View*: Segment list with clickable timecodes and one-click copy per segment.
  - *Continuous Text*: Clean flowing paragraphs optimized for reading or feeding into LLMs.
- **Real-Time Search**: Instant keyword filtering and highlighting with a live match counter.
- **Multi-Format Export**:
  - `.txt` (Clean plain text or with timestamps)
  - `.pdf` (Formatted document with video metadata, date, and pagination)
  - `.srt` (Standard SubRip subtitle format)
  - `.vtt` (WebVTT subtitle format)
  - `.json` (Structured data for developers)
  - `.csv` (Tabular format for spreadsheets)
  - `.md` (Markdown with structured metadata)
- **Quick Copy & Local History**: One-click clipboard copy and browser-persisted recent transcription history.

## 📋 Requirements

- Python 3.10 or higher.
- `ffmpeg` installed on the system (`/usr/bin/ffmpeg`).

## 🚀 Installation & Usage

1. Run the quick-start script:
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

2. Open your browser at **[http://localhost:8001](http://localhost:8001)** (or launch it via **Tools Hub**).
