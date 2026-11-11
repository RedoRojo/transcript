import html
import re
from typing import Dict, Any, List, Optional
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    PoTokenRequired,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeRequestFailed,
)


def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extract an 11-character YouTube video ID from various URL formats or a raw ID."""
    if not url_or_id:
        return None
    url_or_id = url_or_id.strip()

    # Direct 11-character ID check
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url_or_id):
        return url_or_id

    patterns = [
        r"(?:v=|\/vi\/|\/v\/|\/embed\/|\/shorts\/|\/live\/)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:[\?&]v=)([0-9A-Za-z_-]{11})",
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
    """Fetch video metadata using the YouTube oEmbed API."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    default_thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    metadata = {
        "video_id": video_id,
        "url": video_url,
        "title": f"Video ({video_id})",
        "author": "YouTube",
        "author_url": "https://www.youtube.com",
        "thumbnail_url": default_thumbnail,
        "is_local": False,
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
        # Fallback gracefully if oEmbed is unreachable
        pass

    return metadata


def _matches_lang_prefix(lang_code: str, prefix: str) -> bool:
    """Return True if lang_code matches prefix exactly or as a subtag."""
    return lang_code == prefix or lang_code.startswith(f"{prefix}-")


def get_transcripts_and_tracks(video_id: str, requested_lang: Optional[str] = None) -> Dict[str, Any]:
    """List available transcript tracks and fetch the selected or best matching transcript."""
    metadata = get_video_metadata(video_id)
    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
    except TranscriptsDisabled:
        raise ValueError("Subtitles and transcripts are disabled for this video.")
    except NoTranscriptFound:
        raise ValueError("No transcript was found for this video.")
    except AgeRestricted:
        raise ValueError("This video is age-restricted and its transcript cannot be fetched anonymously.")
    except (VideoUnavailable, VideoUnplayable):
        raise ValueError("This video is unavailable, private, or unplayable.")
    except InvalidVideoId:
        raise ValueError("The provided video ID or link is invalid.")
    except (IpBlocked, RequestBlocked):
        raise ValueError("YouTube has temporarily blocked transcript requests from this IP address.")
    except PoTokenRequired:
        raise ValueError("YouTube requires a Proof-of-Origin token to access transcripts for this video.")
    except YouTubeRequestFailed as e:
        raise ValueError(f"YouTube request failed: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to fetch YouTube transcripts: {str(e)}")

    available_tracks: List[Dict[str, Any]] = []
    track_map: Dict[str, Any] = {}

    for t in transcript_list:
        track_info = {
            "language": t.language,
            "language_code": t.language_code,
            "is_generated": t.is_generated,
            "display_name": f"{t.language} ({'auto-generated' if t.is_generated else 'manual'})",
        }
        available_tracks.append(track_info)
        track_map[t.language_code] = t

    if not available_tracks:
        raise ValueError("No transcript tracks are available for this video.")

    # Select target track: requested language > manual English/Spanish > any English/Spanish > first available
    target_track = None
    if requested_lang and requested_lang in track_map:
        target_track = track_map[requested_lang]
    else:
        pref_codes = ["en", "en-US", "en-GB", "es", "es-419", "es-ES"]
        for code in pref_codes:
            for t_info in available_tracks:
                if _matches_lang_prefix(t_info["language_code"], code) and not t_info["is_generated"]:
                    target_track = track_map[t_info["language_code"]]
                    break
            if target_track:
                break

        if not target_track:
            for code in pref_codes:
                for t_info in available_tracks:
                    if _matches_lang_prefix(t_info["language_code"], code):
                        target_track = track_map[t_info["language_code"]]
                        break
                if target_track:
                    break

        if not target_track:
            manuals = [t_info for t_info in available_tracks if not t_info["is_generated"]]
            if manuals:
                target_track = track_map[manuals[0]["language_code"]]
            else:
                target_track = track_map[available_tracks[0]["language_code"]]

    # Fetch transcript snippets
    try:
        raw_snippets = target_track.fetch()
    except Exception as e:
        raise ValueError(f"Failed to download transcript ({target_track.language}): {str(e)}")

    segments: List[Dict[str, Any]] = []
    text_pieces: List[str] = []
    total_duration = 0.0

    for snippet in raw_snippets:
        raw_text = getattr(snippet, "text", "") if hasattr(snippet, "text") else snippet.get("text", "")
        start = float(getattr(snippet, "start", 0.0) if hasattr(snippet, "start") else snippet.get("start", 0.0))
        duration = float(getattr(snippet, "duration", 0.0) if hasattr(snippet, "duration") else snippet.get("duration", 0.0))

        # Unescape HTML entities and collapse internal newlines/spaces
        text = html.unescape(raw_text).replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        end = round(start + duration, 2)
        start = round(start, 2)
        duration = round(duration, 2)

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

    return {
        "metadata": metadata,
        "available_languages": available_tracks,
        "current_language": {
            "language": target_track.language,
            "language_code": target_track.language_code,
            "is_generated": target_track.is_generated,
        },
        "segments": segments,
        "full_text": full_text,
        "stats": {
            "total_segments": len(segments),
            "total_words": total_words,
            "total_duration": total_duration,
            "duration_formatted": format_time(total_duration),
        },
    }
