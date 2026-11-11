import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Configure logger
logger = logging.getLogger("local_transcribe")

# Apply an FFmpeg-based decode_audio patch to faster_whisper to guarantee
# broad container/codec support and avoid PyAV incompatibility on newer Python builds.
try:
    import faster_whisper.audio
    import faster_whisper.transcribe
    from faster_whisper import WhisperModel

    def ffmpeg_decode_audio(input_file, sampling_rate: int = 16000, split_stereo: bool = False):
        """Decode any audio/video file directly into a 16 kHz mono float32 array via FFmpeg."""
        cmd = [
            "ffmpeg", "-nostdin", "-threads", "0", "-i", str(input_file),
            "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le", "-ar", str(sampling_rate), "-"
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            raise RuntimeError("FFmpeg was not found in PATH. Please install ffmpeg.")
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to extract audio with FFmpeg: {e}")

        audio = np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
        return audio

    faster_whisper.audio.decode_audio = ffmpeg_decode_audio
    faster_whisper.transcribe.decode_audio = ffmpeg_decode_audio
except ImportError:
    WhisperModel = None
    logger.warning("faster-whisper is not installed or could not be loaded.")

# Thread-safe global model cache to avoid reloading models across requests
_LOADED_MODELS: Dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()

VALID_MODELS = {"tiny", "base", "small", "medium", "large-v3"}

LANGUAGE_NAMES = {
    "es": "Spanish",
    "en": "English",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ca": "Catalan",
    "gl": "Galician",
    "eu": "Basque",
}


def check_ffmpeg_available() -> bool:
    """Return True if both ffmpeg and ffprobe executables are available."""
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def get_whisper_model(model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
    """Fetch or load a cached faster-whisper model safely across threads."""
    if WhisperModel is None:
        raise RuntimeError("faster-whisper is not available in this Python environment.")

    normalized_size = model_size.strip().lower() if model_size else "base"
    if normalized_size not in VALID_MODELS:
        normalized_size = "base"

    cache_key = f"{normalized_size}_{device}_{compute_type}"
    with _MODEL_LOCK:
        if cache_key not in _LOADED_MODELS:
            logger.info("Loading Whisper model '%s' on %s (%s)...", normalized_size, device, compute_type)
            _LOADED_MODELS[cache_key] = WhisperModel(
                normalized_size,
                device=device,
                compute_type=compute_type,
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
    """Inspect duration, audio/video streams, and format using ffprobe."""
    duration = 0.0
    has_video = False
    has_audio = False
    format_name = "unknown"

    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", file_path,
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        probe_data = json.loads(result.stdout)

        if "format" in probe_data:
            duration = float(probe_data["format"].get("duration", 0.0) or 0.0)
            format_name = probe_data["format"].get(
                "format_long_name",
                probe_data["format"].get("format_name", "Media"),
            )

        for stream in probe_data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video":
                has_video = True
            elif codec_type == "audio":
                has_audio = True
    except FileNotFoundError:
        raise RuntimeError("ffprobe was not found in PATH. Please install ffmpeg.")
    except Exception as e:
        logger.warning("Failed to probe media metadata with ffprobe: %s", e)

    return {
        "duration": duration,
        "has_video": has_video,
        "has_audio": has_audio,
        "format_name": format_name,
    }


def generate_video_thumbnail(file_path: str, output_path: str) -> bool:
    """Extract a representative JPEG thumbnail frame from a video file."""
    for seek_args in (["-ss", "00:00:01"], []):
        try:
            cmd = [
                "ffmpeg", "-y", *seek_args, "-i", file_path,
                "-vframes", "1", "-q:v", "2", "-vf", "scale=640:-1", output_path,
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
        except Exception:
            continue
    return False


def transcribe_local_file(
    file_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
    original_filename: Optional[str] = None,
    media_url: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    file_id: Optional[str] = None,
    media_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Transcribe a local video or audio file using faster-whisper.
    Returns a standardized dictionary matching the YouTube transcription payload.
    """
    if not os.path.isfile(file_path):
        raise ValueError(f"The specified file does not exist: {file_path}")

    if not check_ffmpeg_available():
        raise RuntimeError("FFmpeg/ffprobe is not installed or not available in PATH.")

    meta_info = media_info if media_info is not None else extract_media_metadata(file_path)
    if not meta_info.get("has_audio", True):
        raise ValueError("No audio stream was found in this media file.")

    file_size_bytes = os.path.getsize(file_path)
    display_name = original_filename or Path(file_path).name
    file_stem = Path(display_name).stem
    display_title = file_stem.replace("_", " ").replace("-", " ").strip().title() or "Local Media"

    normalized_model = model_size.strip().lower() if model_size else "base"
    if normalized_model not in VALID_MODELS:
        normalized_model = "base"

    model = get_whisper_model(model_size=normalized_model)

    lang_param = (
        language.strip().lower()
        if language and language.strip() and language.strip().lower() != "auto"
        else None
    )

    try:
        segments_generator, info = model.transcribe(
            file_path,
            language=lang_param,
            beam_size=5,
            word_timestamps=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        raw_segments = list(segments_generator)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Whisper transcription failed: {str(e)}")

    detected_lang_code = info.language or (lang_param or "unknown")
    detected_lang_name = LANGUAGE_NAMES.get(detected_lang_code, detected_lang_code.upper())
    confidence_pct = int(round((info.language_probability or 0.0) * 100))

    segments: List[Dict[str, Any]] = []
    text_pieces: List[str] = []
    total_duration = float(meta_info.get("duration", 0.0) or 0.0)

    for seg in raw_segments:
        text = seg.text.strip()
        if not text:
            continue

        start = round(float(seg.start), 2)
        end = round(float(seg.end), 2)
        duration = round(max(0.0, end - start), 2)

        if end > total_duration:
            total_duration = end

        segments.append({
            "index": len(segments) + 1,
            "start": start,
            "end": end,
            "duration": duration,
            "start_formatted": format_time(start),
            "end_formatted": format_time(end),
            "text": text,
        })
        text_pieces.append(text)

    full_text = " ".join(text_pieces)
    total_words = len(full_text.split()) if full_text else 0
    file_ext = Path(display_name).suffix.lower() or Path(file_path).suffix.lower()

    metadata = {
        "video_id": file_id or file_stem,
        "url": display_name,
        "title": display_title,
        "author": f"Local file ({file_ext})" if file_ext else "Local file",
        "author_url": "#",
        "thumbnail_url": thumbnail_url or "",
        "media_url": media_url or "",
        "is_local": True,
        "has_video": bool(meta_info.get("has_video", False)),
        "file_size": file_size_bytes,
    }

    current_lang = {
        "language": f"{detected_lang_name} ({confidence_pct}% confidence)",
        "language_code": detected_lang_code,
        "is_generated": True,
    }

    available_tracks = [
        {
            "language": detected_lang_name,
            "language_code": detected_lang_code,
            "is_generated": True,
            "display_name": f"{detected_lang_name} (Whisper {normalized_model})",
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
            "duration_formatted": format_time(total_duration),
        },
    }


def transcribe_file(
    file_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Validates a local media file, extracts stream info, and transcribes it with Whisper."""
    p = Path(file_path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not check_ffmpeg_available():
        raise RuntimeError("ffmpeg/ffprobe not found in PATH. Install ffmpeg to transcribe local media.")

    media_info = extract_media_metadata(str(p))
    if not media_info.get("has_audio", False):
        raise ValueError(f"No audio stream found in '{p.name}'.")

    lang = None if not language or language.lower() == "auto" else language
    return transcribe_local_file(
        file_path=str(p),
        model_size=model_size,
        language=lang,
        original_filename=p.name,
        media_info=media_info,
    )
