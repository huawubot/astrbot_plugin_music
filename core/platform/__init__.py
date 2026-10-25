from .apple import AppleMusic
from .base import BaseMusicPlayer
from .kugou import KuGouMusic
from .kugou_api import KuGouMusicAPI
from .neko import NekoMusic
from .netease import NetEaseMusic
from .netease_api import NetEaseMusicAPI
from .qqmusic import QQMusic
from .txqq import TXQQMusic

__all__ = [
    "BaseMusicPlayer",
    "NetEaseMusic",
    "NetEaseMusicAPI",
    "QQMusic",
    "KuGouMusicAPI",
    "KuGouMusic",
    "TXQQMusic",
    "NekoMusic",
    "AppleMusic",
]
