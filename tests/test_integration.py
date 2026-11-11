import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_homepage():
    res = client.get("/")
    assert res.status_code == 200
    assert "Transcripción" in res.text
    assert "YouTube" in res.text

def test_static_assets():
    res_css = client.get("/static/css/style.css")
    assert res_css.status_code == 200
    assert "--bg-page" in res_css.text

    res_js = client.get("/static/js/app.js")
    assert res_js.status_code == 200
    assert "transcribe" in res_js.text

def test_invalid_url():
    res = client.post("/api/transcribe", json={"url": "not-a-valid-url"})
    assert res.status_code == 400
    assert "no válido" in res.json()["detail"]

def test_transcribe_and_exports():
    res = client.post("/api/transcribe", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert res.status_code == 200
    data = res.json()
    assert "metadata" in data
    assert "segments" in data
    assert len(data["segments"]) > 0
    assert "available_languages" in data

    formats = ["txt", "srt", "vtt", "json", "csv", "md", "pdf"]
    for fmt in formats:
        res_exp = client.post("/api/export", json={
            "format": fmt,
            "include_timestamps": True,
            "data": data
        })
        assert res_exp.status_code == 200
        assert len(res_exp.content) > 0
        disp = res_exp.headers.get("content-disposition", "")
        assert f".{fmt}" in disp

if __name__ == "__main__":
    test_homepage()
    print("✓ test_homepage passed")
    test_static_assets()
    print("✓ test_static_assets passed")
    test_invalid_url()
    print("✓ test_invalid_url passed")
    test_transcribe_and_exports()
    print("✓ test_transcribe_and_exports passed")
    print("\nAll integration tests passed successfully!")
