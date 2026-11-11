from contextlib import asynccontextmanager
import mimetypes
import os
import re
import shutil
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services.exporter import (
    export_csv,
    export_json,
    export_markdown,
    export_pdf,
    export_srt,
    export_txt,
    export_vtt,
)
from services.local_transcribe import (
    WhisperModel,
    check_ffmpeg_available,
    extract_media_metadata,
    generate_video_thumbnail,
    transcribe_local_file,
)
from services.youtube import extract_video_id, get_transcripts_and_tracks

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMP_MEDIA_DIR = BASE_DIR / "temp_media"
TEMP_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Ensure common media MIME types are registered
mimetypes.add_type("video/x-matroska", ".mkv")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/ogg", ".opus")

# In-memory registry mapping file_id to local media and thumbnail paths
MEDIA_REGISTRY: Dict[str, Dict[str, Any]] = {}


def cleanup_old_temp_files(max_age_seconds: int = 7200) -> None:
    """Remove temporary media files and registry entries older than max_age_seconds."""
    now = time.time()

    expired_ids = [
        fid for fid, info in list(MEDIA_REGISTRY.items())
        if now - info.get("created_at", now) > max_age_seconds
    ]
    for fid in expired_ids:
        MEDIA_REGISTRY.pop(fid, None)

    for item in TEMP_MEDIA_DIR.iterdir():
        try:
            if item.is_file() and (now - item.stat().st_mtime > max_age_seconds):
                item.unlink(missing_ok=True)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_old_temp_files()
    yield


app = FastAPI(
    title="Minimalist Transcript Tool (YouTube & Local Media)",
    version="2.1.0",
    lifespan=lifespan,
)


class TranscribeRequest(BaseModel):
    url: str
    language: Optional[str] = None


class ExportRequest(BaseModel):
    format: str
    include_timestamps: bool = True
    data: Dict[str, Any]


def sanitize_filename(name: str) -> str:
    """Sanitize a string into a safe base filename."""
    clean = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", name or "")
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean[:60] if clean else "transcript"


def build_content_disposition(filename: str) -> str:
    """Build an RFC 5987 Content-Disposition header with a safe ASCII fallback."""
    ascii_fallback = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
    )
    ascii_fallback = re.sub(r'["\\]', "", ascii_fallback)
    if not ascii_fallback or ascii_fallback.startswith("."):
        ext = Path(filename).suffix or ""
        ascii_fallback = f"transcript{ext}"
    encoded = quote(filename, safe="")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'


def _save_upload_file(upload: UploadFile, destination: Path) -> None:
    """Persist an uploaded file stream to disk synchronously."""
    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
    finally:
        upload.file.close()


@app.get("/api/health")
async def health_check():
    """Return service health and local transcription capability status."""
    return {
        "status": "ok",
        "ffmpeg": check_ffmpeg_available(),
        "whisper_available": WhisperModel is not None,
    }


@app.post("/api/transcribe")
async def transcribe_endpoint(req: TranscribeRequest):
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL or video ID. Please enter a link such as youtube.com/watch?v=... or youtu.be/...",
        )

    try:
        result = await run_in_threadpool(
            get_transcripts_and_tracks, video_id, requested_lang=req.language
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.post("/api/transcribe-local")
async def transcribe_local_endpoint(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    file_path: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    model_size: str = Form("base"),
):
    background_tasks.add_task(cleanup_old_temp_files)

    if (not file or not file.filename) and (not file_path or not file_path.strip()):
        raise HTTPException(
            status_code=400,
            detail="You must upload a video/audio file or specify a local file path.",
        )

    file_id = f"local_{uuid.uuid4().hex[:12]}"
    target_path: Optional[Path] = None
    saved_upload_path: Optional[Path] = None
    thumb_path: Optional[Path] = None
    original_name: Optional[str] = None

    if file and file.filename:
        original_name = Path(file.filename).name
        ext = Path(original_name).suffix or ".mp4"
        clean_ext = ext if ext.startswith(".") else f".{ext}"
        saved_upload_path = TEMP_MEDIA_DIR / f"{file_id}{clean_ext}"

        try:
            await run_in_threadpool(_save_upload_file, file, saved_upload_path)
        except Exception as e:
            saved_upload_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

        target_path = saved_upload_path
    elif file_path:
        clean_path = file_path.strip()
        path_obj = Path(clean_path).expanduser().resolve()
        if not path_obj.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"File not found at the specified path: {clean_path}",
            )
        target_path = path_obj
        original_name = path_obj.name

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=400, detail="Could not resolve the local media file.")

    try:
        media_info = await run_in_threadpool(extract_media_metadata, str(target_path))
        if not media_info.get("has_audio", False):
            raise ValueError("No audio stream was found in the selected media file.")

        has_thumb = False
        if media_info.get("has_video", False):
            thumb_path = TEMP_MEDIA_DIR / f"{file_id}_thumb.jpg"
            has_thumb = await run_in_threadpool(
                generate_video_thumbnail, str(target_path), str(thumb_path)
            )
            if not has_thumb:
                thumb_path.unlink(missing_ok=True)
                thumb_path = None

        media_url = f"/api/media/{file_id}"
        thumbnail_url = f"/api/media/{file_id}/thumb" if has_thumb else ""

        result = await run_in_threadpool(
            transcribe_local_file,
            file_path=str(target_path),
            model_size=model_size,
            language=language,
            original_filename=original_name,
            media_url=media_url,
            thumbnail_url=thumbnail_url,
            file_id=file_id,
            media_info=media_info,
        )

        guessed_mime, _ = mimetypes.guess_type(str(target_path))
        MEDIA_REGISTRY[file_id] = {
            "media_path": str(target_path),
            "thumb_path": str(thumb_path) if has_thumb and thumb_path else None,
            "filename": original_name,
            "media_type": guessed_mime or "application/octet-stream",
            "created_at": time.time(),
        }
        return result
    except ValueError as e:
        if saved_upload_path:
            saved_upload_path.unlink(missing_ok=True)
        if thumb_path:
            thumb_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        if saved_upload_path:
            saved_upload_path.unlink(missing_ok=True)
        if thumb_path:
            thumb_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        if saved_upload_path:
            saved_upload_path.unlink(missing_ok=True)
        if thumb_path:
            thumb_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Local transcription failed: {str(e)}")


@app.get("/api/media/{file_id}")
async def serve_media(file_id: str):
    info = MEDIA_REGISTRY.get(file_id)
    if not info or not os.path.isfile(info["media_path"]):
        raise HTTPException(status_code=404, detail="Media file not found.")
    return FileResponse(
        info["media_path"],
        media_type=info.get("media_type", "application/octet-stream"),
    )


@app.get("/api/media/{file_id}/thumb")
async def serve_media_thumb(file_id: str):
    info = MEDIA_REGISTRY.get(file_id)
    if not info or not info.get("thumb_path") or not os.path.isfile(info["thumb_path"]):
        raise HTTPException(status_code=404, detail="Thumbnail not found.")
    return FileResponse(info["thumb_path"], media_type="image/jpeg")


@app.post("/api/export")
async def export_endpoint(req: ExportRequest):
    fmt = req.format.lower().strip()
    data = req.data
    meta = data.get("metadata", {})
    raw_title = meta.get("title", "transcript")
    base_name = sanitize_filename(raw_title)

    if fmt == "txt":
        content = export_txt(data, include_timestamps=req.include_timestamps)
        filename = f"{base_name}.txt"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )
    elif fmt == "srt":
        content = export_srt(data)
        filename = f"{base_name}.srt"
        return Response(
            content=content.encode("utf-8"),
            media_type="application/x-subrip; charset=utf-8",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )
    elif fmt == "vtt":
        content = export_vtt(data)
        filename = f"{base_name}.vtt"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/vtt; charset=utf-8",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )
    elif fmt == "json":
        content = export_json(data)
        filename = f"{base_name}.json"
        return Response(
            content=content.encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )
    elif fmt == "csv":
        content = export_csv(data)
        filename = f"{base_name}.csv"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )
    elif fmt == "md":
        content = export_markdown(data, include_timestamps=req.include_timestamps)
        filename = f"{base_name}.md"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )
    elif fmt == "pdf":
        pdf_bytes = await run_in_threadpool(
            export_pdf, data, include_timestamps=req.include_timestamps
        )
        filename = f"{base_name}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export format: {fmt}")


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
async def root():
    return FileResponse(
        str(STATIC_DIR / "index.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8001))
    reload_enabled = os.environ.get("RELOAD", "0") == "1"
    uvicorn.run("app:app", host=host, port=port, reload=reload_enabled)
