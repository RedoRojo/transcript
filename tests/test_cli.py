"""
Offline-safe CLI and export tests for YouTube & Local Transcript.
Runnable with both unittest and pytest:
    .venv/bin/python -m unittest discover -s tests -v
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
CLI = BASE_DIR / "cli.py"
sys.path.insert(0, str(BASE_DIR))

SAMPLE_DATA = {
    "metadata": {
        "video_id": "dQw4w9WgXcQ",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Sample Lecture Video",
        "author": "Test Channel",
        "is_local": False,
    },
    "current_language": {
        "language": "English",
        "language_code": "en",
        "is_generated": False,
    },
    "available_languages": [],
    "segments": [
        {
            "index": 1,
            "start": 0.0,
            "end": 2.5,
            "duration": 2.5,
            "start_formatted": "00:00",
            "end_formatted": "00:02",
            "text": "Welcome to the sample lecture.",
        },
        {
            "index": 2,
            "start": 2.5,
            "end": 5.0,
            "duration": 2.5,
            "start_formatted": "00:02",
            "end_formatted": "00:05",
            "text": "Today we test the CLI interface.",
        },
    ],
    "full_text": "Welcome to the sample lecture. Today we test the CLI interface.",
    "stats": {
        "total_segments": 2,
        "total_words": 11,
        "total_duration": 5.0,
        "duration_formatted": "00:05",
    },
}


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=60,
    )


class TranscriptCLITests(unittest.TestCase):
    def test_help_for_all_subcommands(self):
        for sub in ([], ["yt"], ["local"], ["formats"]):
            res = run_cli(*sub, "--help")
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("usage:", res.stdout)

    def test_no_command_exits_with_usage_code(self):
        self.assertEqual(run_cli().returncode, 2)

    def test_formats_human_and_json(self):
        res = run_cli("formats", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        for fmt in ("txt", "srt", "vtt", "json", "csv", "md", "pdf"):
            self.assertIn(fmt, payload["formats"])

    def test_export_transcript_all_formats(self):
        from services.exporter import export_transcript, SUPPORTED_EXPORT_FORMATS

        for fmt in SUPPORTED_EXPORT_FORMATS:
            content, filename, mime = export_transcript(SAMPLE_DATA, fmt=fmt, include_timestamps=True)
            self.assertTrue(filename.endswith(f".{fmt}"))
            self.assertTrue(len(content) > 0)
            if fmt == "pdf":
                self.assertIsInstance(content, bytes)
                self.assertTrue(content.startswith(b"%PDF"))
            else:
                self.assertIsInstance(content, str)

    def test_yt_and_local_cli_with_mocked_services(self):
        import cli

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            out_srt = tmp_path / "lecture.srt"

            with patch("services.youtube.transcribe_youtube", return_value=SAMPLE_DATA):
                rc = cli.main(["yt", "dQw4w9WgXcQ", "-o", str(out_srt), "-q"])
            self.assertEqual(rc, 0)
            self.assertTrue(out_srt.is_file())
            self.assertIn("00:00:00,000 --> 00:00:02,500", out_srt.read_text(encoding="utf-8"))

            # Local file transcription with mocked service
            dummy_media = tmp_path / "audio.mp3"
            dummy_media.write_bytes(b"fake-audio")
            out_md = tmp_path / "notes.md"
            with patch("services.local_transcribe.transcribe_file", return_value=SAMPLE_DATA):
                rc2 = cli.main(["local", str(dummy_media), "--model", "tiny", "-o", str(out_md), "-q"])
            self.assertEqual(rc2, 0)
            self.assertTrue(out_md.is_file())
            self.assertIn("# Sample Lecture Video", out_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
