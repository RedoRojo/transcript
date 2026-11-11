# Agent Guide — YouTube & Local Transcript (`tools transcript`)

Fast reference for AI agents invoking or maintaining `transcript`.

## 1. Invoking from an Agent

- **Never start the web server (`./run.sh`)** to transcribe media. Always invoke `tools transcript` (or `./cli.sh`).
- **Two output modes for agents**:
  1. **Save to file + JSON summary**: pass `-f <format> [-o path] --json -q`.
  2. **Stream raw transcript text directly to `stdout`**: pass `-o - -q` (without `--json`), ideal when the agent wants to read or summarize the transcript immediately without creating a file.
- **Exit codes**: `0` = success, `1` = runtime error, `2` = usage error.

### Common Recipes

```bash
# 1. Read a YouTube transcript directly into stdout as clean paragraphs (fastest for LLM summarization)
tools transcript yt "https://www.youtube.com/watch?v=VIDEO_ID" -f txt --no-timestamps -o - -q

# 2. Save a YouTube transcript as SRT, VTT, Markdown, PDF, CSV, or JSON
tools transcript yt "https://youtu.be/VIDEO_ID" -l es -f srt -o subtitles.srt --json -q

# 3. Transcribe a local audio or video file with Whisper (models: tiny, base [default], small, medium)
tools transcript local recording.mp4 -m base -l auto -f md -o notes.md --json -q

# 4. Stream local audio transcription directly to stdout using the fast 'tiny' model
tools transcript local voice_note.m4a -m tiny -f txt --no-timestamps -o - -q

# 5. List supported export formats
tools transcript formats --json
```

### JSON Output Schema (`--json` when saving to a file)

```json
{
  "streamed": false,
  "output": "/abs/path/to/Video_Title.srt",
  "format": "srt",
  "bytes": 18420,
  "title": "Video Title",
  "language": "en",
  "segments": 142,
  "words": 1250,
  "duration": "08:45"
}
```

## 2. Codebase Map

- `services/youtube.py`: `extract_video_id`, `get_transcripts_and_tracks`, `transcribe_youtube`.
- `services/local_transcribe.py`: `transcribe_local_file`, `transcribe_file` (`faster-whisper` INT8 + `ffmpeg`/`ffprobe`).
- `services/exporter.py`: `export_transcript` dispatching `txt`, `srt`, `vtt`, `json`, `csv`, `md`, `pdf`.
- `cli.py` / `cli.sh`: CLI adapter (`argparse`). Uses `.venv/bin/python`.
- `tests/`: Offline-safe test suite. Run with `.venv/bin/python -m pytest -q`.
