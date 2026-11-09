import time
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Dict, Any, List
from pathlib import Path

from backend.core.config import settings

logger = logging.getLogger(__name__)

# In-memory cache for Pexels search responses (24-hour TTL)
_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 86400  # 24 hours


class PexelsService:
    """
    Backend-only service to search and download contextually relevant stock footage from Pexels Video API.
    Preserves creator attribution and honors rate-limiting and 24-hour response caching.
    """

    BASE_URL = "https://api.pexels.com/v1/videos/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else getattr(settings, "PEXELS_API_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.api_key and str(self.api_key).strip())

    def search_videos(
        self,
        query: str,
        orientation: str = "portrait",
        per_page: int = 5,
        min_duration: float = 2.0
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Searches Pexels for stock videos matching query.
        Returns a list of structured video records or None if unavailable/failed.
        """
        if not self.is_configured():
            logger.info("Pexels API key is not configured; skipping stock footage search.")
            return None

        clean_query = query.strip()
        if not clean_query:
            return None

        cache_key = f"{clean_query.lower()}_{orientation}_{per_page}"
        now = time.time()

        # Check cache
        if cache_key in _SEARCH_CACHE:
            cached = _SEARCH_CACHE[cache_key]
            if now - cached["timestamp"] < CACHE_TTL_SECONDS:
                logger.info(f"Returning cached Pexels search for '{clean_query}' ({orientation})")
                return cached["data"]

        params = {
            "query": clean_query,
            "per_page": str(per_page),
        }
        if orientation in ("portrait", "landscape", "square"):
            params["orientation"] = orientation

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": self.api_key,
                "User-Agent": "ClipForge/1.0",
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status != 200:
                    logger.warning(f"Pexels search returned HTTP status {response.status}")
                    return None
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                logger.error(f"Pexels API authentication rejected with HTTP {e.code}.")
            elif e.code == 429:
                logger.warning("Pexels API rate limit exceeded.")
            else:
                logger.warning(f"Pexels API HTTP error {e.code}: {e.reason}")
            return None
        except Exception as e:
            logger.warning(f"Pexels video search network error: {e}")
            return None

        raw_videos = data.get("videos", [])
        if not raw_videos:
            logger.info(f"No Pexels videos found for query '{clean_query}' with orientation {orientation}")
            return []

        results: List[Dict[str, Any]] = []
        for vid in raw_videos:
            duration = float(vid.get("duration", 0))
            if duration < min_duration:
                continue

            video_files = vid.get("video_files", [])
            if not video_files:
                continue

            # Select best MP4 file (prefer HD resolution matching target)
            best_file = None
            for vf in video_files:
                if vf.get("file_type") == "video/mp4" and vf.get("link"):
                    # Check quality
                    if vf.get("quality") == "hd":
                        best_file = vf
                        break
                    elif not best_file:
                        best_file = vf

            if not best_file:
                continue

            creator_user = vid.get("user") or {}
            creator_name = creator_user.get("name") or "Pexels Creator"
            creator_url = creator_user.get("url") or "https://www.pexels.com"
            video_url = vid.get("url") or f"https://www.pexels.com/video/{vid.get('id')}"

            results.append({
                "video_id": vid.get("id"),
                "download_url": best_file["link"],
                "width": best_file.get("width") or vid.get("width"),
                "height": best_file.get("height") or vid.get("height"),
                "duration": duration,
                "creator_name": creator_name,
                "creator_url": creator_url,
                "pexels_video_url": video_url,
                "image_preview": vid.get("image"),
            })

        # Cache results
        _SEARCH_CACHE[cache_key] = {
            "timestamp": now,
            "data": results
        }

        return results

    def download_video(
        self,
        download_url: str,
        target_path: Path,
        max_bytes: int = 60_000_000,
        timeout: int = 30
    ) -> bool:
        """
        Downloads the remote video file into target_path with size boundary and timeout guards.
        """
        if not download_url.startswith("https://"):
            logger.error("Refusing to download non-HTTPS video URL.")
            return False

        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        req = urllib.request.Request(
            download_url,
            headers={
                "User-Agent": "ClipForge/1.0"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to download video, status: {resp.status}")
                    return False

                # Check Content-Length header if present
                content_len = resp.headers.get("Content-Length")
                if content_len and int(content_len) > max_bytes:
                    logger.warning(f"Video file exceeds size limit ({content_len} > {max_bytes})")
                    return False

                total_downloaded = 0
                with open(target_path, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        total_downloaded += len(chunk)
                        if total_downloaded > max_bytes:
                            logger.warning(f"Download aborted: file exceeded {max_bytes} bytes")
                            return False
                        f.write(chunk)

            if target_path.exists() and target_path.stat().st_size > 0:
                logger.info(f"Downloaded Pexels video ({total_downloaded} bytes) to {target_path}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error downloading Pexels video: {e}")
            if target_path.exists():
                try:
                    target_path.unlink()
                except Exception:
                    pass
            return False


pexels_service = PexelsService()
