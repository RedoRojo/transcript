import os
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

# Configure logger
logger = logging.getLogger("local_transcribe")

# Apply FFmpeg-based decode_audio monkeypatch to faster_whisper to ensure
# 100% compatibility with any video/audio format and avoid av 19 issues.
try:
    import faster_whisper.audio
    import faster_whisper.transcribe
    from faster_whisper import WhisperModel

    def ffmpeg_decode_audio(input_file, sampling_rate: int = 16000, split_stereo: bool = False):
        """Decode any audio/video file directly to 16kHz mono float32 numpy array using FFmpeg."""
        cmd = [
            "ffmpeg", "-nostdin", "-threads", "0", "-i", str(input_file),
            "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le", "-ar", str(sampling_rate), "-"
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            raise ValueError(f"No se pudo extraer el audio del archivo con FFmpeg: {e}")

        audio = np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
        return audio

    faster_whisper.audio.decode_audio = ffmpeg_decode_audio
    faster_whisper.transcribe.decode_audio = ffmpeg_decode_audio
except ImportError:
    WhisperModel = None
    logger.warning("faster-whisper no está instalado o no se pudo cargar.")

# Global model cache to avoid reloading models on every request
_LOADED_MODELS: Dict[str, Any] = {}

LANGUAGE_NAMES = {
    "es": "Español",
    "en": "Inglés",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "pt": "Portugués",
    "ru": "Ruso",
    "zh": "Chino",
    "ja": "Japonés",
    "ko": "Coreano",
    "ar": "Árabe",
    "hi": "Hindi",
    "ca": "Catalán",
    "gl": "Gallego",
    "eu": "Euskera"
}

def get_whisper_model(model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
    """Fetch or load a cached faster-whisper model."""
    if WhisperModel is None:
        raise RuntimeError("faster-whisper no está disponible en el entorno.")

    valid_models = {"tiny", "base", "small", "medium", "large-v3"}
    if model_size not in valid_models:
        model_size = "base"

    cache_key = f"{model_size}_{device}_{compute_type}"
    if cache_key not in _LOADED_MODELS:
        logger.info(f"Cargando modelo Whisper '{model_size}' en {device} ({compute_type})...")
        _LOADED_MODELS[cache_key] = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type
        )
    return _LOADED_MODELS[cache_key]

def format_time(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    seconds = int(max(0, seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def extract_media_metadata(file_path: str) -> Dict[str, Any]:
    """Inspect duration, streams, and format using ffprobe."""
    duration = 0.0
    has_video = False
    format_name = "desconocido"

    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        probe_data = json.loads(result.stdout)

        if "format" in probe_data:
            duration = float(probe_data["format"].get("duration", 0.0))
            format_name = probe_data["format"].get("format_long_name", probe_data["format"].get("format_name", "Multimedia"))

        if "streams" in probe_data:
            for stream in probe_data["streams"]:
                if stream.get("codec_type") == "video":
                    has_video = True
                    break
    except Exception as e:
        logger.warning(f"No se pudo consultar metadatos con ffprobe: {e}")

    return {
        "duration": duration,
        "has_video": has_video,
        "format_name": format_name
    }

def generate_video_thumbnail(file_path: str, output_path: str) -> bool:
    """Extract a representative thumbnail image from the video."""
    try:
        cmd = [
            "ffmpeg", "-y", "-ss", "00:00:01", "-i", file_path,
            "-vframes", "1", "-q:v", "2", "-vf", "scale=640:-1", output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        # Fallback to frame at second 0
        try:
            cmd = [
                "ffmpeg", "-y", "-i", file_path,
                "-vframes", "1", "-q:v", "2", "-vf", "scale=640:-1", output_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception:
            return False

def transcribe_local_file(
    file_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
    original_filename: Optional[str] = None,
    media_url: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribes a local video or audio file using faster-whisper.
    Returns a standardized dictionary matching the YouTube transcription structure.
    """
    if not os.path.isfile(file_path):
        raise ValueError(f"El archivo especificado no existe: {file_path}")

    # Inspect media
    meta_info = extract_media_metadata(file_path)
    file_size_bytes = os.path.getsize(file_path)
    file_stem = Path(original_filename or file_path).stem
    display_title = file_stem.replace("_", " ").replace("-", " ").strip().title() or "Video Local"

    # Load model
    model = get_whisper_model(model_size=model_size)

    # Clean language argument
    lang_param = language.strip().lower() if language and language.strip() and language.strip().lower() != "auto" else None

    # Run transcription
    try:
        segments_generator, info = model.transcribe(
            file_path,
            language=lang_param,
            beam_size=5,
            word_timestamps=False,
            vad_filter=True, # Voice Activity Detection filter to remove silence
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        raw_segments = list(segments_generator)
    except Exception as e:
        raise ValueError(f"Error durante el procesamiento con Whisper: {str(e)}")

    detected_lang_code = info.language
    detected_lang_name = LANGUAGE_NAMES.get(detected_lang_code, detected_lang_code.upper())

    segments = []
    text_pieces = []
    total_duration = meta_info["duration"]

    for idx, seg in enumerate(raw_segments):
        text = seg.text.strip()
        if not text:
            continue

        start = round(seg.start, 2)
        end = round(seg.end, 2)
        duration = round(end - start, 2)

        if end > total_duration:
            total_duration = end

        segments.append({
            "index": idx + 1,
            "start": start,
            "end": end,
            "duration": duration,
            "start_formatted": format_time(start),
            "end_formatted": format_time(end),
            "text": text
        })
        text_pieces.append(text)

    full_text = " ".join(text_pieces)
    total_words = len(full_text.split())

    metadata = {
        "video_id": file_id or file_stem,
        "url": original_filename or Path(file_path).name,
        "title": display_title,
        "author": f"Archivo local ({Path(file_path).suffix.lower()})",
        "author_url": "#",
        "thumbnail_url": thumbnail_url or "",
        "media_url": media_url or "",
        "is_local": True,
        "has_video": meta_info["has_video"],
        "file_size": file_size_bytes
    }

    current_lang = {
        "language": f"{detected_lang_name} (precisión: {int(info.language_probability * 100)}%)",
        "language_code": detected_lang_code,
        "is_generated": True
    }

    available_tracks = [
        {
            "language": detected_lang_name,
            "language_code": detected_lang_code,
            "is_generated": True,
            "display_name": f"{detected_lang_name} (Whisper {model_size})"
        }
    ]

    return {
        "metadata": metadata,
        "available_languages": available_tracks,
        "current_language": current_lang,
        "segments": segments,
        "full_text": full_text,
        "stats": {
            "total_segments": len(segments),
            "total_words": total_words,
            "total_duration": total_duration,
            "duration_formatted": format_time(total_duration)
        }
    }
