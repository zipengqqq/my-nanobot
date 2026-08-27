from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageAttachment:
    """一张仅供当前轮模型请求使用的图片。"""

    data: bytes
    mime_type: str
