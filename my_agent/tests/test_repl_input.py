from __future__ import annotations

from PIL import Image

from my_agent.agent.media import ImageAttachment
from my_agent.repl.input import (
    ReplInputState,
    _finalize_user_text,
    handle_bracketed_paste,
    persist_images,
)


def test_persist_images_stores_pasted_image_under_controlled_directory(tmp_path) -> None:
    attachment = ImageAttachment(data=b"image-bytes", mime_type="image/png")

    persisted = persist_images([attachment], tmp_path)

    assert len(persisted) == 1
    assert persisted[0].data == b"image-bytes"
    assert persisted[0].mime_type == "image/png"
    assert persisted[0].local_path is not None
    assert persisted[0].local_path.parent.parent == tmp_path.resolve()
    assert persisted[0].local_path.read_bytes() == b"image-bytes"


def test_bracketed_paste_attaches_clipboard_image() -> None:
    image = ImageAttachment(data=b"image-bytes", mime_type="image/png")
    buffer = type("Buffer", (), {"text": "", "insert_text": lambda self, text: setattr(self, "text", self.text + text)})()
    event = type("Event", (), {"data": "", "current_buffer": buffer})()
    reader = type("Reader", (), {"read_image": lambda self: image})()
    state = ReplInputState()

    handle_bracketed_paste(event, reader, state)

    assert buffer.text == "[Image #1]"
    assert state.images == [image]


def test_finalize_user_text_attaches_local_windows_image_path(tmp_path) -> None:
    image_path = tmp_path / "portrait - copy.png"
    Image.new("RGB", (1, 1), color="white").save(image_path)
    state = ReplInputState()

    text = _finalize_user_text(f"{image_path} generate a poster", state)

    assert text == "[Image #1] generate a poster"
    assert len(state.images) == 1
    assert state.images[0].mime_type == "image/png"
