from typing import ClassVar

import aiohttp

from astrbot.api import logger

from ..config import PluginConfig
from ..model import Platform, Song
from .base import BaseMusicPlayer


class NetEaseMusic(BaseMusicPlayer):
    """
    网易云音乐
    """

    platform: ClassVar[Platform] = Platform(
        name="netease",
        display_name="网易云音乐",
    )

    def __init__(self, config: PluginConfig):
        super().__init__(config)

    async def _resolve_cover_url(self, cover_url: str) -> str:
        """Resolve a NetEase cover URL to its final redirect target.

        Args:
            cover_url: Original cover URL returned by the metadata service.

        Returns:
            The final URL after redirects, or the original URL on failure.
        """
        try:
            async with self._get_session().get(
                cover_url,
                allow_redirects=True,
                proxy=self.platform_cfg.proxy or None,
            ) as cover_response:
                cover_response.raise_for_status()
                return str(cover_response.url)
        except (aiohttp.ClientError, TimeoutError) as exc:
            logger.warning(
                f"NetEase cover redirect failed ({type(exc).__name__}); "
                "using the original URL"
            )
            return cover_url

    async def fetch_songs(self, keyword: str, limit=5, extra=None) -> list[Song]:
        result = await self._request(
            url="http://music.163.com/api/search/get/web",
            method="POST",
            data={"s": keyword, "limit": limit, "type": 1, "offset": 0},
            cookies={"appver": "2.0.2"},
        )
        if (
            not isinstance(result, dict)
            or "result" not in result
            or "songs" not in result["result"]
        ):
            logger.error(f"返回了意料之外数据：{result}")
            return []

        songs = result["result"]["songs"][:limit]
        return [
            Song(
                id=s.get("id"),
                source=self.platform.name,
                name=s.get("name"),
                artists="、".join(a["name"] for a in s["artists"]),
                duration=s.get("duration"),
                page_url=f"https://music.163.com/song?id={s['id']}"
                if s.get("id")
                else None,
            )
            for s in songs
        ]

    async def fetch_extra(self, song: Song) -> Song:
        """Fetch audio, cover, and lyrics metadata from the shared service.

        Args:
            song: NetEase song whose metadata should be completed.

        Returns:
            The song with any missing metadata populated.
        """
        url = f"https://api.qijieya.cn/meting/?type=song&id={song.id}"
        result = await self._request(url)

        if isinstance(result, list) and result:
            data = result[0]
            if not song.audio_url:
                song.audio_url = data.get("url")
            if not song.cover_url:
                cover_url = data.get("pic")
                if isinstance(cover_url, str) and cover_url:
                    song.cover_url = await self._resolve_cover_url(cover_url)
            if not song.lyrics:
                song.lyrics = data.get("lrc")
        return song

    async def fetch_comments(self, song: Song) -> Song:
        """Fetch popular comments from NetEase's comment endpoint.

        Args:
            song: NetEase song whose comments should be fetched.

        Returns:
            The song with comments populated when available.
        """
        if song.comments:
            return song

        try:
            result = await self._request(
                url=f"https://music.163.com/weapi/v1/resource/hotcomments/R_SO_4_{song.id}?csrf_token=",
                method="POST",
                data={
                    "params": self.platform_cfg.enc_params if self.platform_cfg else "",
                    "encSecKey": self.platform_cfg.enc_sec_key
                    if self.platform_cfg
                    else "",
                },
            )
        except Exception as exc:
            logger.warning(f"{self.__class__.__name__} fetch_comments failed: {exc}")
            return song

        comments = result.get("hotComments") if isinstance(result, dict) else []
        if comments:
            song.comments = comments
        return song

    async def fetch_lyrics(self, song: Song) -> Song:
        """Fetch lyrics from the shared NetEase lyrics service.

        Args:
            song: NetEase song whose lyrics should be fetched.

        Returns:
            The song with lyrics populated when available.
        """
        if song.lyrics:
            return song

        url = f"https://api.qijieya.cn/meting/?server=netease&type=lrc&id={song.id}"
        try:
            result = await self._request(url)
            lyrics = result.get("lyric") if isinstance(result, dict) else str(result)
            song.lyrics = lyrics
        except Exception as exc:
            logger.warning(f"{self.__class__.__name__} fetch_lyrics failed: {exc}")
        return song
