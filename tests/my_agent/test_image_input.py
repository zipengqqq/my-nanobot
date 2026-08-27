from io import BytesIO

from PIL import Image
from prompt_toolkit.output.win32 import NoConsoleScreenBufferError

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.media import ImageAttachment
from my_agent.agent.provider import ModelResponse, ProviderAdapter
from my_agent.agent.runner import AgentRunner
from my_agent.repl.input import (
    ClipboardImageReader,
    ReplInputState,
    handle_clipboard_paste,
    insert_pasted_text,
)
from my_agent.repl.input import prompt_with_images
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


class CapturingProvider(ProviderAdapter):
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] | None = None

    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        self.messages = messages
        _ = tools
        return ModelResponse(text="图片已识别")


def test_context_builder_encodes_pasted_image_as_openai_image_url() -> None:
    image = ImageAttachment(data=b"\x89PNG\r\n\x1a\n", mime_type="image/png")

    messages = ContextBuilder().build_messages(
        history=[],
        user_text="[Image #1] 请识别图片",
        images=[image],
    )

    assert messages[1] == {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="},
            },
            {"type": "text", "text": "[Image #1] 请识别图片"},
        ],
    }


def test_agent_loop_keeps_pasted_image_out_of_session_history() -> None:
    provider = CapturingProvider()
    session_manager = SessionManager()
    loop = AgentLoop(
        session_manager=session_manager,
        context_builder=ContextBuilder(),
        runner=AgentRunner(provider=provider, tool_registry=ToolRegistry()),
    )
    image = ImageAttachment(data=b"\x89PNG\r\n\x1a\n", mime_type="image/png")

    reply = loop.handle_user_message(
        session_id="image-test",
        user_text="[Image #1] 这是什么？",
        images=[image],
    )

    assert reply == "图片已识别"
    assert provider.messages is not None
    content = provider.messages[1]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "image_url"

    history = session_manager.get_history("image-test")
    assert [message.content for message in history] == ["[Image #1] 这是什么？", "图片已识别"]


def test_clipboard_reader_converts_clipboard_image_to_png_attachment() -> None:
    reader = ClipboardImageReader(
        grabclipboard=lambda: Image.new("RGB", (2, 1), color=(255, 0, 0)),
    )

    attachment = reader.read_image()

    assert attachment is not None
    assert attachment.mime_type == "image/png"
    with Image.open(BytesIO(attachment.data)) as decoded:
        assert decoded.size == (2, 1)


def test_clipboard_reader_ignores_non_image_clipboard_content() -> None:
    reader = ClipboardImageReader(grabclipboard=lambda: ["C:/example.txt"])

    assert reader.read_image() is None


def test_repl_input_state_labels_images_in_paste_order() -> None:
    state = ReplInputState()
    first = ImageAttachment(data=b"first", mime_type="image/png")
    second = ImageAttachment(data=b"second", mime_type="image/png")

    assert state.add_image(first) == "[Image #1]"
    assert state.add_image(second) == "[Image #2]"
    assert state.images == [first, second]


def test_prompt_with_images_falls_back_when_prompt_toolkit_has_no_console(monkeypatch) -> None:
    class FailingSession:
        def prompt(self, *args: object, **kwargs: object) -> str:
            _ = args
            _ = kwargs
            raise NoConsoleScreenBufferError()

    monkeypatch.setattr("prompt_toolkit.PromptSession", FailingSession)
    monkeypatch.setattr("builtins.input", lambda prompt="": "fallback text")

    assert prompt_with_images() == ("fallback text", [])


def test_prompt_with_images_attaches_file_url_after_input_fallback(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "fallback.png"
    Image.new("RGB", (1, 1), color=(255, 255, 0)).save(image_path)

    class FailingSession:
        def prompt(self, *args: object, **kwargs: object) -> str:
            _ = args
            _ = kwargs
            raise NoConsoleScreenBufferError()

    monkeypatch.setattr("prompt_toolkit.PromptSession", FailingSession)
    monkeypatch.setattr("builtins.input", lambda prompt="": f"{image_path.as_uri()}识别")

    text, images = prompt_with_images()

    assert text == "[Image #1]识别"
    assert len(images) == 1


def test_insert_pasted_text_uses_event_data_and_normalizes_line_endings() -> None:
    inserted: list[str] = []
    state = ReplInputState()

    class Event:
        data = "first\r\nsecond\rthird"
        current_buffer = type("Buffer", (), {"insert_text": inserted.append})()

    insert_pasted_text(Event(), state)

    assert inserted == ["first\nsecond\nthird"]
    assert state.images == []


def test_insert_pasted_text_attaches_local_image_file_url(tmp_path) -> None:
    image_path = tmp_path / "PixPin^capture.png"
    Image.new("RGB", (1, 1), color=(0, 0, 255)).save(image_path)
    inserted: list[str] = []
    state = ReplInputState()

    class Event:
        data = f"{image_path.as_uri().replace('%5E', '^')}提取文字"
        current_buffer = type("Buffer", (), {"insert_text": inserted.append})()

    insert_pasted_text(Event(), state)

    assert inserted == ["[Image #1]提取文字"]
    assert len(state.images) == 1
    assert state.images[0].mime_type == "image/png"


def test_clipboard_paste_inserts_image_placeholder_and_attaches_image() -> None:
    class Buffer:
        def __init__(self) -> None:
            self.inserted = ""

        def insert_text(self, text: str) -> None:
            self.inserted += text

    class Event:
        current_buffer = Buffer()

    reader = ClipboardImageReader(
        grabclipboard=lambda: Image.new("RGB", (1, 1), color=(0, 255, 0)),
    )
    state = ReplInputState()

    handle_clipboard_paste(Event(), reader, state, paste_mode=None)

    assert Event.current_buffer.inserted == "[Image #1]"
    assert len(state.images) == 1
    assert state.images[0].mime_type == "image/png"
