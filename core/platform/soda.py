import json
import re
from typing import ClassVar
from urllib.parse import urlencode

from astrbot.api import logger

from ..model import Platform, Song
from .base import BaseMusicPlayer


class SodaMusic(BaseMusicPlayer):
    """Search Soda Music and resolve its official audition audio URLs."""

    platform: ClassVar[Platform] = Platform(name="soda", display_name="汽水音乐")
    SEARCH_URL = "https://api.qishui.com/luna/search/track"
    TRACK_PAGE_URL = "https://music.douyin.com/qishui/share/track"

    @staticmethod
    def _extract_audio_url(page: str) -> str | None:
        """Extract the audition URL embedded in a Soda Music share page.

        Args:
            page: HTML returned by the Soda Music share page.

        Returns:
            The embedded audio URL, or None if the page has no usable URL.
        """
        match = re.search(r"_ROUTER_DATA\s*=\s*({.*?});", page, re.DOTALL)
        if not match:
            return None
        try:
            metadata = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.debug("Soda Music share page contained invalid router data")
            return None

        loader_data = metadata.get("loaderData")
        track_page = (
            loader_data.get("track_page") if isinstance(loader_data, dict) else None
        )
        option = (
            track_page.get("audioWithLyricsOption")
            if isinstance(track_page, dict)
            else None
        )
        audio_url = option.get("url") if isinstance(option, dict) else None
        if not isinstance(audio_url, str) or not audio_url.startswith(
            ("http://", "https://")
        ):
            return None
        return audio_url.replace(r"\u002F", "/").replace("%7C", "|").replace("%3D", "=")

    async def fetch_songs(
        self, keyword: str, limit: int, extra: str | None = None
    ) -> list[Song]:
        """Search Soda Music tracks.

        Args:
            keyword: Song or artist search text.
            limit: Maximum number of results to return.
            extra: Unused platform-specific command context.

        Returns:
            Matching Soda Music tracks.
        """
        del extra
        limit = max(1, min(limit, 20))
        params = {
            "device_platform": "android",
            "os": "android",
            "aid": "386088",
            "app_name": "luna",
            "version_code": "100198030",
            "version_name": "19.8.0",
            "device_type": "ABR-AL80",
            "device_brand": "HUAWEI",
            "language": "zh",
            "os_api": "35",
            "os_version": "15",
            "channel": "xiaomi_8478_64",
            "iid": "2204957404569386",
            "device_id": "2204957404565290",
            "q": keyword,
            "cursor": 0,
            "count": limit,
        }
        try:
            result = await self._request(f"{self.SEARCH_URL}?{urlencode(params)}")
        except Exception as exc:
            logger.warning(f"Soda Music search failed: {exc}")
            return []

        groups = result.get("result_groups") if isinstance(result, dict) else None
        items = (
            groups[0].get("data", [])
            if isinstance(groups, list) and groups and isinstance(groups[0], dict)
            else []
        )
        songs = []
        for item in items:
            entity = item.get("entity") if isinstance(item, dict) else None
            track = entity.get("track", {}) if isinstance(entity, dict) else {}
            if not isinstance(track, dict) or not track.get("id"):
                continue
            artists = track.get("artists") or []
            album = track.get("album") or {}
            cover = album.get("url_cover") or {}
            cover_url = ""
            if isinstance(cover, dict):
                urls = cover.get("urls") or []
                cover_uri = cover.get("uri") or ""
                cover_base = urls[0] if urls else ""
                if cover_base and cover_uri:
                    cover_url = (
                        f"{cover_base.rstrip('/')}/{cover_uri.lstrip('/')}"
                        "~c5_500x500.jpg"
                    )
                else:
                    cover_url = cover_base or cover_uri
            artist_names = [
                artist["name"]
                for artist in artists
                if isinstance(artist, dict) and artist.get("name")
            ]
            try:
                duration = int(float(track.get("duration") or 0) * 1000)
            except (TypeError, ValueError):
                duration = None
            song_id = str(track["id"])
            songs.append(
                Song(
                    id=song_id,
                    source=self.platform.name,
                    card_type="qq",
                    name=track.get("name"),
                    artists="、".join(artist_names),
                    duration=duration or None,
                    cover_url=cover_url or None,
                    page_url=f"{self.TRACK_PAGE_URL}?track_id={song_id}",
                    note=album.get("name") if isinstance(album, dict) else None,
                )
            )
            if len(songs) >= limit:
                break
        return songs

    async def fetch_extra(self, song: Song) -> Song:
        """Resolve the official Soda Music audition URL from its share page.

        Args:
            song: Soda Music track returned by search.

        Returns:
            The song with its audition URL populated when available.
        """
        if song.audio_url:
            return song
        try:
            page = await self._request(
                f"{self.TRACK_PAGE_URL}?track_id={song.id}",
                headers={
                    **self.HEADERS,
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
                    "Mobile/15E148 Safari/604.1",
                },
            )
        except Exception as exc:
            logger.warning(f"Soda Music audition lookup failed: {exc}")
            return song

        audio_url = self._extract_audio_url(page) if isinstance(page, str) else None
        if audio_url:
            song.audio_url = audio_url
            song.note = song.note or "汽水音乐试听片段"
        return song

    async def fetch_comments(self, song: Song) -> Song:
        """Return the song because this integration has no comments endpoint.

        Args:
            song: Soda Music track.

        Returns:
            The unchanged song.
        """
        return song

    async def fetch_lyrics(self, song: Song) -> Song:
        """Return the song because lyric support is outside the MVP.

        Args:
            song: Soda Music track.

        Returns:
            The unchanged song.
        """
        return song
