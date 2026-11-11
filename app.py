import os
import re
import uuid
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.youtube import extract_video_id, get_transcripts_and_tracks
from services.local_transcribe import (
    transcribe_local_file,
    generate_video_thumbnail
)
from services.exporter import (
    export_txt, export_srt, export_vtt, export_json, export_csv, export_pdf, export_markdown
)

app = FastAPI(title="Minimalist Transcript Tool (YouTube & Local Media)", version="2.0.0")

# Setup temporary media directory
TEMP_MEDIA_DIR = Path("temp_media")
TEMP_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Registry to map file_id to file info
MEDIA_REGISTRY: Dict[str, Dict[str, Any]] = {}

class TranscribeRequest(BaseModel):
    url: str
    language: Optional[str] = None

class ExportRequest(BaseModel):
    format: str
    include_timestamps: bool = True
    data: Dict[str, Any]

def sanitize_filename(name: str) -> str:
    """Sanitize string to safe filename."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r'\s+', "_", name.strip())
    return name[:60] if name else "transcripcion"

def cleanup_old_temp_files():
    """Remove temporary uploaded files older than 2 hours."""
    now = time.time()
    for item in TEMP_MEDIA_DIR.iterdir():
        try:
            if item.is_file() and (now - item.stat().st_mtime > 7200):
                item.unlink(missing_ok=True)
        except Exception:
            pass

@app.post("/api/transcribe")
async def transcribe_endpoint(req: TranscribeRequest):
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(
            status_code=400,
            detail="Enlace de YouTube no válido. Asegúrate de ingresar un enlace como youtube.com/watch?v=... o youtu.be/..."
        )

    try:
        result = get_transcripts_and_tracks(video_id, requested_lang=req.language)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocurrió un error inesperado: {str(e)}")

@app.post("/api/transcribe-local")
async def transcribe_local_endpoint(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    file_path: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    model_size: str = Form("base")
):
    background_tasks.add_task(cleanup_old_temp_files)

    if not file and (not file_path or not file_path.strip()):
        raise HTTPException(
            status_code=400,
            detail="Debes proporcionar un archivo de video/audio o especificar una ruta de archivo local."
        )

    file_id = f"local_{uuid.uuid4().hex[:12]}"
    target_path = None
    original_name = None

    if file and file.filename:
        original_name = file.filename
        ext = Path(original_name).suffix or ".mp4"
        clean_ext = ext if ext.startswith(".") else f".{ext}"
        saved_file_path = TEMP_MEDIA_DIR / f"{file_id}{clean_ext}"

        try:
            with open(saved_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al guardar el archivo subido: {str(e)}")
        finally:
            file.file.close()

        target_path = saved_file_path
    elif file_path:
        clean_path = file_path.strip()
        path_obj = Path(clean_path).expanduser().resolve()
        if not path_obj.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"No se encontró el archivo en la ruta especificada: {clean_path}"
            )
        target_path = path_obj
        original_name = path_obj.name

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=400, detail="No se pudo resolver el archivo multimedia local.")

    # Generate thumbnail
    thumb_path = TEMP_MEDIA_DIR / f"{file_id}_thumb.jpg"
    has_thumb = generate_video_thumbnail(str(target_path), str(thumb_path))

    # Register media in cache for streaming / thumbnail access
    MEDIA_REGISTRY[file_id] = {
        "media_path": str(target_path),
        "thumb_path": str(thumb_path) if has_thumb else None,
        "filename": original_name
    }

    media_url = f"/api/media/{file_id}"
    thumbnail_url = f"/api/media/{file_id}/thumb" if has_thumb else ""

    try:
        result = transcribe_local_file(
            file_path=str(target_path),
            model_size=model_size,
            language=language,
            original_filename=original_name,
            media_url=media_url,
            thumbnail_url=thumbnail_url,
            file_id=file_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante la transcripción local: {str(e)}")

@app.get("/api/media/{file_id}")
async def serve_media(file_id: str):
    info = MEDIA_REGISTRY.get(file_id)
    if not info or not os.path.isfile(info["media_path"]):
        raise HTTPException(status_code=404, detail="Archivo multimedia no encontrado.")
    return FileResponse(info["media_path"], filename=info.get("filename"))

@app.get("/api/media/{file_id}/thumb")
async def serve_media_thumb(file_id: str):
    info = MEDIA_REGISTRY.get(file_id)
    if not info or not info.get("thumb_path") or not os.path.isfile(info["thumb_path"]):
        raise HTTPException(status_code=404, detail="Miniatura no encontrada.")
    return FileResponse(info["thumb_path"], media_type="image/jpeg")

@app.post("/api/export")
async def export_endpoint(req: ExportRequest):
    fmt = req.format.lower().strip()
    data = req.data
    meta = data.get("metadata", {})
    raw_title = meta.get("title", "transcripcion")
    base_name = sanitize_filename(raw_title)

    if fmt == "txt":
        content = export_txt(data, include_timestamps=req.include_timestamps)
        filename = f"{base_name}.txt"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "srt":
        content = export_srt(data)
        filename = f"{base_name}.srt"
        return Response(
            content=content.encode("utf-8"),
            media_type="application/x-subrip; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "vtt":
        content = export_vtt(data)
        filename = f"{base_name}.vtt"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/vtt; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "json":
        content = export_json(data)
        filename = f"{base_name}.json"
        return Response(
            content=content.encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "csv":
        content = export_csv(data)
        filename = f"{base_name}.csv"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "md":
        content = export_markdown(data, include_timestamps=req.include_timestamps)
        filename = f"{base_name}.md"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "pdf":
        pdf_bytes = export_pdf(data, include_timestamps=req.include_timestamps)
        filename = f"{base_name}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    else:
        raise HTTPException(status_code=400, detail=f"Formato no soportado: {fmt}")

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
        "static/index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
