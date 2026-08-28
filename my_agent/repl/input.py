"""终端 REPL 的图片输入处理。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from PIL import Image

from my_agent.agent.media import ImageAttachment

_FILE_IMAGE_URL = re.compile(
    r"file:///[^\s]*?\.(?:png|jpe?g|gif|webp|bmp|tiff?)",
    re.IGNORECASE,
)
_LOCAL_IMAGE_PATH = re.compile(
    r"[a-z]:[\\/][^\r\n]*?\.(?:png|jpe?g|gif|webp|bmp|tiff?)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ClipboardImageReader:
    """读取系统剪贴板中的位图并转换为 PNG。"""

    grabclipboard: Callable[[], Any] | None = None

    def read_image(self) -> ImageAttachment | None:
        grab = self.grabclipboard
        if grab is None:
            try:
                from PIL import ImageGrab

                grab = ImageGrab.grabclipboard
            except (ImportError, OSError):
                return None
        try:
            value = grab()
        except OSError:
            return None
        if not isinstance(value, Image.Image):
            return None
        output = BytesIO()
        value.save(output, format="PNG")
        return ImageAttachment(data=output.getvalue(), mime_type="image/png")


@dataclass(slots=True)
class ReplInputState:
    images: list[ImageAttachment] = field(default_factory=list)

    def add_image(self, image: ImageAttachment) -> str:
        self.images.append(image)
        return f"[Image #{len(self.images)}]"


def _load_local_image_path(path: Path) -> ImageAttachment | None:
    try:
        with Image.open(path) as source:
            source.load()
            output = BytesIO()
            source.save(output, format="PNG")
    except (OSError, ValueError):
        return None
    return ImageAttachment(data=output.getvalue(), mime_type="image/png")


def _load_local_image_file_url(value: str) -> ImageAttachment | None:
    parsed = urlparse(value)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        return None

    return _load_local_image_path(Path(url2pathname(unquote(parsed.path))))


def _replace_file_image_urls(text: str, state: ReplInputState) -> str:
    def replace(match: re.Match[str]) -> str:
        image = _load_local_image_file_url(match.group())
        return state.add_image(image) if image is not None else match.group()

    return _FILE_IMAGE_URL.sub(replace, text)


def _replace_local_image_paths(text: str, state: ReplInputState) -> str:
    def replace(match: re.Match[str]) -> str:
        image = _load_local_image_path(Path(match.group()))
        return state.add_image(image) if image is not None else match.group()

    return _LOCAL_IMAGE_PATH.sub(replace, text)


def _finalize_user_text(text: str, state: ReplInputState) -> str:
    return _replace_local_image_paths(_replace_file_image_urls(text.strip(), state), state)


def persist_images(images: list[ImageAttachment], output_dir: Path) -> list[ImageAttachment]:
    """将本轮附件保存到受控目录，以便图像工具作为参考图读取。"""
    if not images:
        return []

    dated_dir = output_dir.resolve() / datetime.now().astimezone().strftime("%Y-%m-%d")
    dated_dir.mkdir(parents=True, exist_ok=True)
    persisted: list[ImageAttachment] = []
    for image in images:
        extension = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }.get(image.mime_type, ".png")
        path = dated_dir / f"input_{uuid.uuid4().hex[:12]}{extension}"
        path.write_bytes(image.data)
        persisted.append(
            ImageAttachment(
                data=image.data,
                mime_type=image.mime_type,
                local_path=path.resolve(),
            )
        )
    return persisted


def insert_pasted_text(event: Any, state: ReplInputState) -> None:
    """插入终端发送的文本粘贴内容，并附加本地图片 URL 指向的图片。"""
    text = str(event.data).replace("\r\n", "\n").replace("\r", "\n")
    event.current_buffer.insert_text(_replace_file_image_urls(text, state))


def handle_clipboard_paste(
    event: Any,
    reader: ClipboardImageReader,
    state: ReplInputState,
    paste_mode: Any,
) -> None:
    """优先将剪贴板图片作为本轮附件；否则使用终端默认文本粘贴。"""
    image = reader.read_image()
    if image is not None:
        event.current_buffer.insert_text(state.add_image(image))
        return
    event.current_buffer.paste_clipboard_data(
        event.app.clipboard.get_data(), paste_mode=paste_mode
    )


def handle_bracketed_paste(
    event: Any,
    reader: ClipboardImageReader,
    state: ReplInputState,
) -> None:
    """处理终端宿主转发的粘贴事件，并优先识别剪贴板图片。"""
    image = reader.read_image()
    if image is not None:
        event.current_buffer.insert_text(state.add_image(image))
        return
    insert_pasted_text(event, state)


def prompt_with_images(
    prompt: str = "你> ",
    *,
    clipboard_reader: ClipboardImageReader | None = None,
) -> tuple[str, list[ImageAttachment]]:
    """读取一行文本，并将 Ctrl+V 粘贴的图片作为当前轮附件返回。"""
    reader = clipboard_reader or ClipboardImageReader()
    state = ReplInputState()

    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.keys import Keys
        from prompt_toolkit.output.win32 import NoConsoleScreenBufferError
        from prompt_toolkit.selection import PasteMode
    except ImportError:
        text = input(prompt)
        return _finalize_user_text(text, state), state.images

    bindings = KeyBindings()

    @bindings.add("c-v")
    def paste(event: Any) -> None:
        handle_clipboard_paste(event, reader, state, PasteMode.EMACS)

    @bindings.add(Keys.BracketedPaste)
    def bracketed_paste(event: Any) -> None:
        handle_bracketed_paste(event, reader, state)

    try:
        text = PromptSession().prompt(prompt, key_bindings=bindings)
    except (EOFError, NoConsoleScreenBufferError):
        text = input(prompt)
    return _finalize_user_text(text, state), state.images
