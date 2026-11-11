import os
import subprocess
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app import MEDIA_REGISTRY, TEMP_MEDIA_DIR, app

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_registered_test_media():
    """Remove test media and thumbnails added to MEDIA_REGISTRY during each test."""
    existing_ids = set(MEDIA_REGISTRY.keys())
    yield
    for file_id in list(MEDIA_REGISTRY.keys()):
        if file_id in existing_ids:
            continue
        info = MEDIA_REGISTRY.pop(file_id, None) or {}
        for key in ("media_path", "thumb_path"):
            p = info.get(key)
            if p and os.path.isfile(p) and os.path.dirname(os.path.abspath(p)) == str(TEMP_MEDIA_DIR):
                os.remove(p)


@pytest.fixture(scope="module")
def sample_wav_path():
    """Create a temporary 2-second audio file using ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-ar", "16000", "-ac", "1", path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    yield path

    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="module")
def sample_silent_mp4_path():
    """Create a 1-second video-only MP4 with no audio stream."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=1",
        "-pix_fmt", "yuv420p", path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    yield path

    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="module")
def sample_av_mp4_path():
    """Create a 1-second MP4 containing both video and audio streams."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=800:duration=1",
        "-pix_fmt", "yuv420p", "-shortest", path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    yield path

    if os.path.exists(path):
        os.remove(path)


def test_transcribe_local_missing_params():
    res = client.post("/api/transcribe-local", data={})
    assert res.status_code == 400
    assert "You must upload a video/audio file" in res.json()["detail"]


def test_transcribe_local_invalid_filepath():
    res = client.post("/api/transcribe-local", data={"file_path": "/path/to/nonexistent/file.mp4"})
    assert res.status_code == 400
    assert "File not found at the specified path" in res.json()["detail"]


def test_transcribe_local_directory_rejected(tmp_path):
    res = client.post("/api/transcribe-local", data={"file_path": str(tmp_path)})
    assert res.status_code == 400
    assert "File not found at the specified path" in res.json()["detail"]


def test_transcribe_local_video_without_audio(sample_silent_mp4_path):
    res = client.post(
        "/api/transcribe-local",
        data={"file_path": sample_silent_mp4_path, "model_size": "tiny"},
    )
    assert res.status_code == 400
    assert "No audio stream" in res.json()["detail"]


def test_transcribe_local_with_filepath(sample_wav_path):
    res = client.post(
        "/api/transcribe-local",
        data={
            "file_path": sample_wav_path,
            "model_size": "tiny",
            "language": "en",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "metadata" in data
    assert data["metadata"]["is_local"] is True
    assert data["metadata"]["has_video"] is False
    assert "segments" in data
    assert "stats" in data
    assert "full_text" in data

    # Test export of local transcription across all supported formats
    for fmt in ["txt", "srt", "vtt", "json", "csv", "md", "pdf"]:
        res_exp = client.post(
            "/api/export",
            json={
                "format": fmt,
                "include_timestamps": True,
                "data": data,
            },
        )
        assert res_exp.status_code == 200
        assert len(res_exp.content) > 0


def test_transcribe_local_with_upload(sample_wav_path):
    with open(sample_wav_path, "rb") as f:
        res = client.post(
            "/api/transcribe-local",
            files={"file": ("test_audio.wav", f, "audio/wav")},
            data={"model_size": "tiny", "language": "auto"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["metadata"]["is_local"] is True
    assert data["metadata"]["has_video"] is False
    assert data["metadata"]["title"] == "Test Audio"

    # Verify media route
    media_url = data["metadata"]["media_url"]
    res_media = client.get(media_url)
    assert res_media.status_code == 200
    assert len(res_media.content) > 0


def test_transcribe_local_video_and_thumbnail(sample_av_mp4_path):
    with open(sample_av_mp4_path, "rb") as f:
        res = client.post(
            "/api/transcribe-local",
            files={"file": ("clip_demo.mp4", f, "video/mp4")},
            data={"model_size": "tiny", "language": "en"},
        )
    assert res.status_code == 200
    data = res.json()
    meta = data["metadata"]
    assert meta["is_local"] is True
    assert meta["has_video"] is True
    assert meta["thumbnail_url"].endswith("/thumb")

    res_thumb = client.get(meta["thumbnail_url"])
    assert res_thumb.status_code == 200
    assert res_thumb.headers.get("content-type", "").startswith("image/jpeg")
    assert len(res_thumb.content) > 0

    res_video = client.get(meta["media_url"])
    assert res_video.status_code == 200
    assert "attachment" not in res_video.headers.get("content-disposition", "")
