import os
import sys
import tempfile
import subprocess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

@pytest.fixture(scope="module")
def sample_wav_path():
    """Create a temporary 2-second audio file using ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-ar", "16000", "-ac", "1", path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    yield path

    if os.path.exists(path):
        os.remove(path)

def test_transcribe_local_missing_params():
    res = client.post("/api/transcribe-local", data={})
    assert res.status_code == 400
    assert "Debes proporcionar un archivo" in res.json()["detail"]

def test_transcribe_local_invalid_filepath():
    res = client.post("/api/transcribe-local", data={"file_path": "/path/to/nonexistent/file.mp4"})
    assert res.status_code == 400
    assert "No se encontró el archivo" in res.json()["detail"]

def test_transcribe_local_with_filepath(sample_wav_path):
    res = client.post("/api/transcribe-local", data={
        "file_path": sample_wav_path,
        "model_size": "tiny",
        "language": "en"
    })
    assert res.status_code == 200
    data = res.json()
    assert "metadata" in data
    assert data["metadata"]["is_local"] is True
    assert "segments" in data
    assert "stats" in data
    assert "full_text" in data

    # Test export of local transcription
    for fmt in ["txt", "srt", "vtt", "json", "csv", "md", "pdf"]:
        res_exp = client.post("/api/export", json={
            "format": fmt,
            "include_timestamps": True,
            "data": data
        })
        assert res_exp.status_code == 200
        assert len(res_exp.content) > 0

def test_transcribe_local_with_upload(sample_wav_path):
    with open(sample_wav_path, "rb") as f:
        res = client.post(
            "/api/transcribe-local",
            files={"file": ("test_audio.wav", f, "audio/wav")},
            data={"model_size": "tiny", "language": "auto"}
        )
    assert res.status_code == 200
    data = res.json()
    assert data["metadata"]["is_local"] is True
    assert data["metadata"]["title"] == "Test Audio"

    # Verify media route
    media_url = data["metadata"]["media_url"]
    res_media = client.get(media_url)
    assert res_media.status_code == 200
    assert len(res_media.content) > 0
