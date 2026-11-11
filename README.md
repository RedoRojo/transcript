# Video & Audio Transcription (YouTube & Local Media)

Minimalist toolkit for transcribing **YouTube** videos from a URL or video ID, as well as **local video and audio files** using AI powered by **Whisper (`faster-whisper`)**, from the **browser** or the **command line**.

## ✨ Features

- **Minimalist Design**: Clean zinc/slate aesthetic with automatic and manual **Light Mode** and **Dark Mode** support.
- **Dual Media Input**:
  - **YouTube**: Supports standard URLs (`youtube.com/watch?v=...`), shortened links (`youtu.be/...`), Shorts (`youtube.com/shorts/...`), embedded links, and raw video IDs.
  - **Local Files**: Drag & Drop any media file or specify a local disk path directly (MP4, MKV, WebM, AVI, MOV, MP3, WAV, M4A, FLAC, etc.).
- **Local Whisper Engine (`faster-whisper`)**:
  - CPU-accelerated inference with INT8 quantization (`tiny`, `base`, `small`, `medium`).
  - Automatic language detection or manual selection, plus Voice Activity Detection (VAD).
- **Synced Local Player & Real-Time Search**: Built-in media player synced with clickable timestamps and live keyword filtering.
- **Multi-Format Export**: `.txt`, `.srt`, `.vtt`, `.json`, `.csv`, `.md`, and `.pdf`.

## 📋 Requirements

- Python 3.10 or higher.
- `ffmpeg` installed on the system (`/usr/bin/ffmpeg`).

## 🌐 Web Interface

```bash
./run.sh
```

Open your browser at **[http://localhost:8001](http://localhost:8001)** (or launch it via **Tools Hub**).

## ⌨️ Command Line Interface

Via the global Tools Hub dispatcher (recommended):

```bash
tools transcript yt "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format srt
tools transcript yt dQw4w9WgXcQ --lang es --no-timestamps -o - | grep "palabra"
tools transcript local lecture.mp4 --model base --lang es --format md [-o lecture.md]
tools transcript formats [--json]
```

Or standalone from this repository: `./cli.sh <command> ...`.

| Subcommand | Key Options | Description |
| :--- | :--- | :--- |
| `yt` | `-l/--lang`, `-f/--format`, `--no-timestamps`, `-o FILE\|-` | Fetch and export a YouTube video transcript |
| `local` | `-m/--model tiny\|base\|small\|medium`, `-l/--lang`, `-f/--format`, `-o` | Transcribe local video/audio file(s) with Whisper |
| `formats` | `--json` | List all supported export formats (`txt`, `srt`, `vtt`, `json`, `csv`, `md`, `pdf`) |

All subcommands write output files to the **current working directory** by default (without overwriting existing files), support `-o -` to stream text directly to `stdout` for piping, and accept `--json`, `-q/--quiet`, and `-v/--verbose`.

## 🧪 Running Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```
