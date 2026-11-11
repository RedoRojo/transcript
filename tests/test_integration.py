import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app import app, build_content_disposition
from services.exporter import export_markdown, export_pdf, export_srt, export_txt
from services.youtube import extract_video_id

client = TestClient(app)


class _FakeTrack:
    def __init__(self, language, language_code, is_generated, snippets):
        self.language = language
        self.language_code = language_code
        self.is_generated = is_generated
        self._snippets = snippets

    def fetch(self):
        return self._snippets


def _build_fake_youtube_api():
    """Return a mock YouTubeTranscriptApi instance with multiple language tracks."""
    en_snippets = [
        SimpleNamespace(text="Hello &amp; welcome\neveryone!", start=0.0, duration=2.5),
        SimpleNamespace(text="   Second   line <test>  ", start=2.5, duration=2.0),
    ]
    es_snippets = [
        SimpleNamespace(text="Hola y bienvenidos", start=0.0, duration=2.5),
    ]

    class FakeTranscriptApi:
        def list(self, video_id):
            return [
                _FakeTrack("Spanish (auto-generated)", "es-419", True, es_snippets),
                _FakeTrack("English", "en", False, en_snippets),
            ]

    return FakeTranscriptApi


def test_homepage():
    res = client.get("/")
    assert res.status_code == 200
    assert '<html lang="en">' in res.text
    assert "Transcription" in res.text
    assert "YouTube" in res.text
    assert "no-cache" in res.headers.get("cache-control", "")


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["ffmpeg"], bool)
    assert isinstance(payload["whisper_available"], bool)


def test_static_assets():
    res_css = client.get("/static/css/style.css")
    assert res_css.status_code == 200
    assert "--bg-page" in res_css.text

    res_js = client.get("/static/js/app.js")
    assert res_js.status_code == 200
    assert "transcribeYouTube" in res_js.text


def test_extract_video_id_variants():
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=12s") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/jNQXAC9IVRw?si=abc") == "jNQXAC9IVRw"
    assert extract_video_id("https://www.youtube.com/shorts/abcdefghijk") == "abcdefghijk"
    assert extract_video_id("not-a-valid-url") is None


def test_invalid_url():
    res = client.post("/api/transcribe", json={"url": "not-a-valid-url"})
    assert res.status_code == 400
    assert "Invalid YouTube URL" in res.json()["detail"]


def test_transcribe_and_exports_offline():
    fake_oembed = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "title": "Sample — Demo & Overview",
            "author_name": "Test Channel",
            "author_url": "https://www.youtube.com/@test",
            "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        },
    )

    with (
        patch("services.youtube.YouTubeTranscriptApi", _build_fake_youtube_api()),
        patch("services.youtube.requests.get", return_value=fake_oembed),
    ):
        res = client.post(
            "/api/transcribe",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["metadata"]["title"] == "Sample — Demo & Overview"
    assert data["metadata"]["is_local"] is False
    assert data["current_language"]["language_code"] == "en"
    assert len(data["segments"]) == 2
    assert data["segments"][0]["text"] == "Hello & welcome everyone!"
    assert data["segments"][1]["text"] == "Second line <test>"

    formats = ["txt", "srt", "vtt", "json", "csv", "md", "pdf"]
    for fmt in formats:
        res_exp = client.post(
            "/api/export",
            json={"format": fmt, "include_timestamps": True, "data": data},
        )
        assert res_exp.status_code == 200
        assert len(res_exp.content) > 0
        disp = res_exp.headers.get("content-disposition", "")
        assert f".{fmt}" in disp
        assert "filename*=UTF-8''" in disp


def test_unsupported_export_format():
    res = client.post(
        "/api/export",
        json={"format": "docx", "include_timestamps": True, "data": {"metadata": {}, "segments": []}},
    )
    assert res.status_code == 400
    assert "Unsupported export format" in res.json()["detail"]


def test_build_content_disposition_unicode():
    header = build_content_disposition("Demo — Café & 100%.pdf")
    assert 'filename="Demo__Cafe_&_100%.pdf"' in header or 'filename="Demo' in header
    assert "filename*=UTF-8''Demo" in header


def test_empty_and_xml_special_exports():
    empty_data = {
        "metadata": {"title": "Empty <Audio> & Test", "author": "Local & File", "url": "sample.wav", "is_local": True},
        "current_language": {"language": "English (99% confidence)"},
        "stats": {"duration_formatted": "00:02", "total_words": 0},
        "segments": [],
    }
    assert "No speech segments" in export_txt(empty_data)
    assert "[No speech detected]" in export_srt(empty_data)
    md = export_markdown(empty_data)
    assert "- **File**: `sample.wav`" in md

    pdf_ts = export_pdf(empty_data, include_timestamps=True)
    pdf_plain = export_pdf(empty_data, include_timestamps=False)
    assert pdf_ts.startswith(b"%PDF")
    assert pdf_plain.startswith(b"%PDF")


if __name__ == "__main__":
    test_homepage()
    print("✓ test_homepage passed")
    test_health_endpoint()
    print("✓ test_health_endpoint passed")
    test_static_assets()
    print("✓ test_static_assets passed")
    test_extract_video_id_variants()
    print("✓ test_extract_video_id_variants passed")
    test_invalid_url()
    print("✓ test_invalid_url passed")
    test_transcribe_and_exports_offline()
    print("✓ test_transcribe_and_exports_offline passed")
    print("\nAll integration tests passed successfully!")
