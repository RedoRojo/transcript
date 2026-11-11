import re
from typing import Dict, Any, List, Optional
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    InvalidVideoId,
    IpBlocked,
    YouTubeRequestFailed
)

def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extract 11-character YouTube video ID from various URL formats or raw ID."""
    if not url_or_id:
        return None
    url_or_id = url_or_id.strip()

    # Direct 11 character ID check
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url_or_id):
        return url_or_id

    patterns = [
        r"(?:v=|\/vi\/|\/v\/|\/embed\/|\/shorts\/|\/live\/)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:[\?&]v=)([0-9A-Za-z_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return None

def format_time(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    seconds = int(max(0, seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def get_video_metadata(video_id: str) -> Dict[str, Any]:
    """Fetch video metadata using YouTube oEmbed API."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    default_thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    metadata = {
        "video_id": video_id,
        "url": video_url,
        "title": f"Video ({video_id})",
        "author": "YouTube",
        "author_url": "https://www.youtube.com",
        "thumbnail_url": default_thumbnail
    }

    try:
        oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
        resp = requests.get(oembed_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            metadata["title"] = data.get("title", metadata["title"])
            metadata["author"] = data.get("author_name", metadata["author"])
            metadata["author_url"] = data.get("author_url", metadata["author_url"])
            metadata["thumbnail_url"] = data.get("thumbnail_url", default_thumbnail)
    except Exception:
        # Fallback gracefully
        pass

    return metadata

def get_transcripts_and_tracks(video_id: str, requested_lang: Optional[str] = None) -> Dict[str, Any]:
    """
    List available transcript tracks and fetch the selected or best matching transcript.
    """
    metadata = get_video_metadata(video_id)
    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
    except TranscriptsDisabled:
        raise ValueError("El video tiene los subtítulos y transcripciones desactivados por el autor.")
    except NoTranscriptFound:
        raise ValueError("No se encontró ninguna transcripción disponible para este video.")
    except VideoUnavailable:
        raise ValueError("El video no está disponible o es privado.")
    except InvalidVideoId:
        raise ValueError("El ID o enlace del video es inválido.")
    except IpBlocked:
        raise ValueError("YouTube ha limitado temporalmente el acceso a transcripciones desde esta IP.")
    except Exception as e:
        raise ValueError(f"Error al consultar subtítulos de YouTube: {str(e)}")

    available_tracks = []
    track_map = {}

    for t in transcript_list:
        track_info = {
            "language": t.language,
            "language_code": t.language_code,
            "is_generated": t.is_generated,
            "display_name": f"{t.language} ({'autogenerado' if t.is_generated else 'manual'})"
        }
        available_tracks.append(track_info)
        track_map[t.language_code] = t

    if not available_tracks:
        raise ValueError("No hay pistas de transcripción disponibles para este video.")

    # Determine track to fetch
    target_track = None
    if requested_lang and requested_lang in track_map:
        target_track = track_map[requested_lang]
    else:
        # Preference: Spanish, then English, then first manual, then first available
        pref_codes = ['es', 'es-419', 'es-ES', 'en', 'en-US', 'en-GB']
        for code in pref_codes:
            for t_info in available_tracks:
                if t_info["language_code"].startswith(code) and not t_info["is_generated"]:
                    target_track = track_map[t_info["language_code"]]
                    break
            if target_track:
                break

        if not target_track:
            for code in pref_codes:
                for t_info in available_tracks:
                    if t_info["language_code"].startswith(code):
                        target_track = track_map[t_info["language_code"]]
                        break
                if target_track:
                    break

        if not target_track:
            # Fallback to first manual or first track
            manuals = [t_info for t_info in available_tracks if not t_info["is_generated"]]
            if manuals:
                target_track = track_map[manuals[0]["language_code"]]
            else:
                target_track = track_map[available_tracks[0]["language_code"]]

    # Fetch snippets
    try:
        raw_snippets = target_track.fetch()
    except Exception as e:
        raise ValueError(f"Error al descargar la transcripción ({target_track.language}): {str(e)}")

    segments = []
    text_pieces = []
    total_duration = 0.0

    for idx, snippet in enumerate(raw_snippets):
        # Raw snippet object or dict
        text = getattr(snippet, 'text', '') if hasattr(snippet, 'text') else snippet.get('text', '')
        start = getattr(snippet, 'start', 0.0) if hasattr(snippet, 'start') else snippet.get('start', 0.0)
        duration = getattr(snippet, 'duration', 0.0) if hasattr(snippet, 'duration') else snippet.get('duration', 0.0)

        # Clean text
        text = text.replace('\n', ' ').strip()
        if not text:
            continue

        end = round(start + duration, 2)
        start = round(start, 2)
        duration = round(duration, 2)

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

    return {
        "metadata": metadata,
        "available_languages": available_tracks,
        "current_language": {
            "language": target_track.language,
            "language_code": target_track.language_code,
            "is_generated": target_track.is_generated
        },
        "segments": segments,
        "full_text": full_text,
        "stats": {
            "total_segments": len(segments),
            "total_words": total_words,
            "total_duration": total_duration,
            "duration_formatted": format_time(total_duration)
        }
    }
