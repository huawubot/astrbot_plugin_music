from typing import Any, ClassVar
from urllib.parse import quote

from astrbot.api import logger

from ..config import PluginConfig
from ..model import Platform, Song
from .base import BaseMusicPlayer


class KuGouMusicAPI(BaseMusicPlayer):
    """KuGou Music integration backed by a KuGouMusicApi service."""

    platform: ClassVar[Platform] = Platform(
        name="kugou_api",
        display_name="酷狗音乐API版",
    )

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.base_url = (self.platform_cfg.base_url or "").strip().rstrip("/")

    async def _request_api(self, path: str, params: dict[str, Any]):
        """Request one KuGouMusicApi endpoint and return its JSON body."""
        if not self.base_url:
            logger.warning("KuGouMusicApi base URL is not configured")
            return None
        try:
            request_params = dict(params)
            if self.platform_cfg.cookies:
                request_params["cookie"] = self.platform_cfg.cookies.strip()
            async with self._get_session().get(
                f"{self.base_url}{path}",
                params=request_params,
                proxy=self.platform_cfg.proxy or None,
            ) as response:
                if response.status != 200:
                    logger.warning(f"KuGouMusicApi returned HTTP {response.status}")
                    return None
                return await response.json(content_type=None)
        except Exception as exc:
            logger.warning(f"KuGouMusicApi request failed: {exc}")
            return None

    async def fetch_songs(
        self, keyword: str, limit: int, extra: str | None = None
    ) -> list[Song]:
        """Search KuGou Music through KuGouMusicApi.

        Args:
            keyword: Song or artist search text.
            limit: Maximum number of results to return.
            extra: Unused platform-specific command context.

        Returns:
            Matching KuGou Music songs.
        """
        del extra
        result = await self._request_api(
            "/search", {"keywords": keyword, "type": "song", "pagesize": limit}
        )
        body = result.get("data", result) if isinstance(result, dict) else None
        items = (
            body.get("lists") or body.get("info") or []
            if isinstance(body, dict)
            else []
        )
        songs: list[Song] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            song_hash = str(item.get("hash") or item.get("FileHash") or "")
            if not song_hash:
                continue
            artists = item.get("singername") or item.get("SingerName") or ""
            album = item.get("album_name") or item.get("AlbumName") or ""
            cover = item.get("Image") or item.get("img") or ""
            if cover:
                cover = cover.replace("{size}", "400")
                if cover.startswith("//"):
                    cover = f"https:{cover}"
            duration = item.get("duration") or item.get("Duration")
            songs.append(
                Song(
                    id=song_hash,
                    source=self.platform.name,
                    name=item.get("songname") or item.get("FileName") or "未知歌曲",
                    artists=artists,
                    duration=int(duration) * 1000 if duration else None,
                    cover_url=cover or None,
                    page_url=f"https://www.kugou.com/song/#hash={quote(song_hash)}",
                    note=album,
                )
            )
        return songs

    async def fetch_extra(self, song: Song) -> Song:
        """Resolve audio URL and cover details for a selected song.

        Args:
            song: Song returned by the KuGou search endpoint.

        Returns:
            The song enriched with playback metadata when available.
        """
        if song.audio_url:
            return song
        result = await self._request_api("/song/url", {"hash": song.id})
        body = result.get("data", result) if isinstance(result, dict) else None
        if isinstance(body, list):
            body = body[0] if body else None
        if isinstance(body, dict):
            song.audio_url = body.get("url") or body.get("play_url")
            song.cover_url = song.cover_url or body.get("img") or body.get("cover")
            song.name = song.name or body.get("song_name")
            song.artists = song.artists or body.get("author_name")
        return song

    async def fetch_lyrics(self, song: Song) -> Song:
        """Fetch lyrics using the search and download endpoints.

        Args:
            song: Selected KuGou song.

        Returns:
            The song with decoded lyrics when available.
        """
        if song.lyrics:
            return song
        result = await self._request_api("/search/lyric", {"hash": song.id})
        body = result.get("data", result) if isinstance(result, dict) else None
        if isinstance(body, dict):
            candidates = body.get("candidates") or body.get("result") or []
        else:
            candidates = []
        if not candidates or not isinstance(candidates[0], dict):
            return song
        lyric = candidates[0]
        result = await self._request_api(
            "/lyric",
            {
                "id": lyric.get("id"),
                "accesskey": lyric.get("accesskey"),
                "decode": 1,
                "fmt": "lrc",
            },
        )
        body = result.get("data", result) if isinstance(result, dict) else None
        if isinstance(body, dict):
            song.lyrics = body.get("decodeContent") or body.get("content")
        return song
