#!/usr/bin/env python3
"""
YouTube & Local Transcript - Command Line Interface.

Thin synchronous adapter over services/: transcribes YouTube videos or local
audio/video files (Whisper) and exports to TXT, SRT, VTT, JSON, CSV, MD, or PDF.
Never imports app.py or FastAPI.

Examples:
    tools transcript yt "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format srt
    tools transcript yt dQw4w9WgXcQ -o - | grep -i "never"
    tools transcript local lecture.mp4 --model base --lang es --format md
    tools transcript formats
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

__version__ = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

PROG = os.environ.get("TOOLS_PROG", "cli.sh")
EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_INTERRUPTED = 0, 1, 2, 130

EXPORT_FORMATS = ("txt", "srt", "vtt", "json", "csv", "md", "pdf")
WHISPER_MODELS = ("tiny", "base", "small", "medium")


class CLIError(Exception):
    """Expected runtime error: printed without a traceback, exits with code 1."""


def log(args, message: str) -> None:
    if not getattr(args, "quiet", False):
        print(message, file=sys.stderr, flush=True)


def emit(args, payload: dict, human: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif human:
        print(human)


def resolve_output(requested: Optional[str], default_name: str) -> Path:
    """Explicit -o is used as-is (dirs get default_name); otherwise write to cwd without overwriting."""
    if requested:
        path = Path(requested).expanduser()
        if path.is_dir():
            path = path / default_name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    path = Path.cwd() / default_name
    stem, suffix, counter = path.stem, path.suffix, 1
    while path.exists():
        path = path.with_name(f"{stem}-{counter}{suffix}")
        counter += 1
    return path.resolve()


def _write_or_stream_export(args, data: dict, requested_out: Optional[str]) -> dict:
    from services.exporter import export_transcript

    fmt = args.format
    if not fmt and requested_out and requested_out != "-":
        ext = Path(requested_out).suffix.lower().lstrip(".")
        if ext in EXPORT_FORMATS:
            fmt = ext
    fmt = (fmt or "txt").lower()

    content, suggested_name, _ = export_transcript(
        data,
        fmt=fmt,
        include_timestamps=args.timestamps,
    )

    if requested_out == "-":
        if fmt == "pdf" and sys.stdout.isatty():
            raise CLIError("refusing to write binary PDF data to a terminal stdout (redirect to a file or omit -o -).")
        if isinstance(content, bytes):
            sys.stdout.buffer.write(content)
            sys.stdout.buffer.flush()
        else:
            sys.stdout.write(content)
            if not content.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
        return {"streamed": True, "format": fmt}

    out_path = resolve_output(requested_out, suggested_name)
    if isinstance(content, bytes):
        out_path.write_bytes(content)
    else:
        out_path.write_text(content, encoding="utf-8")

    return {
        "streamed": False,
        "output": str(out_path),
        "format": fmt,
        "bytes": out_path.stat().st_size,
        "title": data.get("metadata", {}).get("title", ""),
        "language": data.get("current_language", {}).get("language_code", ""),
        "segments": data.get("stats", {}).get("total_segments", 0),
        "words": data.get("stats", {}).get("total_words", 0),
        "duration": data.get("stats", {}).get("duration_formatted", "00:00"),
    }


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_yt(args) -> int:
    from services.youtube import transcribe_youtube

    log(args, f"Fetching YouTube transcript for '{args.url_or_id}'...")
    try:
        data = transcribe_youtube(args.url_or_id, language=args.lang)
        summary = _write_or_stream_export(args, data, args.output)
    except Exception as e:
        raise CLIError(str(e))

    if summary["streamed"]:
        return EXIT_OK

    log(
        args,
        f"Saved {summary['format'].upper()} ({summary['segments']} segments, {summary['words']} words):",
    )
    emit(args, summary, summary["output"])
    return EXIT_OK


def cmd_local(args) -> int:
    from services.local_transcribe import transcribe_file

    files = [Path(f).expanduser() for f in args.files]
    for f in files:
        if not f.is_file():
            raise CLIError(f"file not found: {f}")

    if len(files) > 1 and args.output and args.output != "-" and not Path(args.output).expanduser().is_dir():
        raise CLIError("when transcribing multiple files, -o must be a directory (or omitted).")

    results = []
    human_lines = []
    for f in files:
        log(args, f"Transcribing '{f.name}' with Whisper ({args.model})...")
        try:
            data = transcribe_file(str(f), model_size=args.model, language=args.lang)
            summary = _write_or_stream_export(args, data, args.output)
        except Exception as e:
            raise CLIError(str(e))

        if not summary["streamed"]:
            log(
                args,
                f"Saved {summary['format'].upper()} ({summary['segments']} segments, {summary['words']} words):",
            )
            results.append(summary)
            human_lines.append(summary["output"])

    if results:
        payload = results[0] if len(results) == 1 else {"items": results, "count": len(results)}
        emit(args, payload, "\n".join(human_lines))
    return EXIT_OK


def cmd_formats(args) -> int:
    descriptions = {
        "txt": "Plain text (clean paragraphs or timestamped lines)",
        "srt": "SubRip subtitle format (.srt)",
        "vtt": "WebVTT subtitle format (.vtt)",
        "json": "Full structured transcription payload (.json)",
        "csv": "Tabular segments spreadsheet (.csv)",
        "md": "Markdown document with metadata header (.md)",
        "pdf": "Formatted monochrome PDF document (.pdf)",
    }
    human = "\n".join(f"{k:<6} {v}" for k, v in descriptions.items())
    emit(args, {"formats": descriptions}, human)
    return EXIT_OK


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def add_common_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="print machine-readable JSON summary to stdout")
    p.add_argument("-q", "--quiet", action="store_true", help="suppress progress messages on stderr")
    p.add_argument("-v", "--verbose", action="store_true", help="show full tracebacks on errors")


def add_export_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("-f", "--format", choices=EXPORT_FORMATS,
                   help="export format (default: from -o extension, else txt)")
    p.add_argument("--timestamps", dest="timestamps", action="store_true", default=True,
                   help="include timestamps in txt/md/pdf exports (default)")
    p.add_argument("--no-timestamps", dest="timestamps", action="store_false",
                   help="omit timestamps in txt/md/pdf exports (clean paragraphs)")
    p.add_argument("-o", "--output",
                   help="output file or directory ('-' writes transcript content to stdout)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="YouTube & Local Transcript CLI — transcribe YouTube videos or local media files.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # yt
    p_yt = sub.add_parser("yt", help="fetch and export a YouTube video transcript")
    p_yt.add_argument("url_or_id", help="YouTube video URL or 11-character video ID")
    p_yt.add_argument("-l", "--lang", help="preferred language code (e.g. es, en)")
    add_export_flags(p_yt)
    add_common_flags(p_yt)
    p_yt.set_defaults(func=cmd_yt)

    # local
    p_loc = sub.add_parser("local", help="transcribe local audio/video file(s) with Whisper")
    p_loc.add_argument("files", nargs="+", help="local video or audio file path(s)")
    p_loc.add_argument("-m", "--model", choices=WHISPER_MODELS, default="base",
                       help="Whisper model size (default: base)")
    p_loc.add_argument("-l", "--lang", default="auto",
                       help="language code or 'auto' (default: auto)")
    add_export_flags(p_loc)
    add_common_flags(p_loc)
    p_loc.set_defaults(func=cmd_local)

    # formats
    p_fmt = sub.add_parser("formats", help="list supported export formats")
    add_common_flags(p_fmt)
    p_fmt.set_defaults(func=cmd_formats)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    try:
        return args.func(args) or EXIT_OK
    except CLIError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception as e:
        if getattr(args, "verbose", False):
            raise
        print(f"error: {e} (use -v for details)", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
