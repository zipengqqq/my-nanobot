from __future__ import annotations

import json
from pathlib import Path

import httpx

from my_agent.config.settings import Settings
from my_agent.tools import image_generation_tool
from my_agent.tools.image_generation_tool import (
    ImageGenerationTool,
    validate_public_url,
)

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdacd\xfc\xff\x1f\x00\x03\x03"
    b"\x02\x00\xef\xbf\xa7\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_generate_image_polls_task_and_stores_downloaded_image(
    tmp_path: Path, monkeypatch
) -> None:
    requests: list[httpx.Request] = []
    logged_messages: list[str] = []

    def capture_info(message: str, *args: object) -> None:
        logged_messages.append(message % args)

    monkeypatch.setattr(
        image_generation_tool,
        "logger",
        type("Logger", (), {"info": staticmethod(capture_info)})(),
        raising=False,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert request.url == httpx.URL("https://www.rightapi.ai/draw/v1/images/generations")
            assert request.headers["authorization"] == "Bearer test-key"
            assert json.loads(request.content) == {
                "model": "gpt-image-2",
                "prompt": "draw a lighthouse",
                "n": 1,
                "size": "16:9",
                "imageSize": "2K",
                "async": True,
            }
            return httpx.Response(200, json={"task_id": "task_123", "status": "processing"})
        if request.url == httpx.URL("https://www.rightapi.ai/v1/tasks/task_123"):
            return httpx.Response(
                200,
                json={
                    "created": 1_756_000_000,
                    "data": [{"url": "https://cdn.example.test/image.png"}],
                },
            )
        if request.url == httpx.URL("https://cdn.example.test/image.png"):
            return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    tool = ImageGenerationTool(
        workspace=tmp_path,
        api_key="test-key",
        output_dir=tmp_path / "generated-images",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        poll_interval_seconds=0,
        url_validator=lambda _url: None,
    )

    result = tool.run(
        {
            "prompt": "draw a lighthouse",
            "aspect_ratio": "16:9",
            "image_size": "2K",
        }
    )
    assert not result.startswith("ERROR:")
    result_payload = json.loads(result)

    artifact = result_payload["artifacts"][0]
    assert artifact["model"] == "gpt-image-2"
    assert artifact["mime_type"] == "image/png"
    assert Path(artifact["path"]).is_absolute()
    assert (tmp_path / artifact["path"]).read_bytes() == PNG_BYTES
    assert [request.method for request in requests] == ["POST", "GET", "GET"]
    assert logged_messages == ["Image generation task submitted task_id=task_123"]


def test_generate_image_uses_configured_draw_and_task_urls(tmp_path: Path) -> None:
    draw_url = "https://draw.example.test/v1/images"
    task_url_template = "https://tasks.example.test/v1/jobs"
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert request.url == httpx.URL(draw_url)
            return httpx.Response(200, json={"task_id": "task_456", "status": "processing"})
        if request.url == httpx.URL("https://tasks.example.test/v1/jobs/task_456"):
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "data": [{"url": "https://cdn.example.test/image.png"}],
                },
            )
        if request.url == httpx.URL("https://cdn.example.test/image.png"):
            return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    tool = ImageGenerationTool(
        workspace=tmp_path,
        api_key="test-key",
        output_dir=tmp_path / "generated-images",
        draw_url=draw_url,
        task_url_template=task_url_template,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        poll_interval_seconds=0,
        url_validator=lambda _url: None,
    )

    result = json.loads(tool.run({"prompt": "draw a lighthouse"}))

    assert result["artifacts"]
    assert [request.method for request in requests] == ["POST", "GET", "GET"]


def test_settings_loads_image_endpoint_urls_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "OPENAI_BASE_URL=https://api.example.test/v1",
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=test-model",
                "MY_AGENT_SESSION_ID=test-session",
                "MY_AGENT_HISTORY_LIMIT=10",
                "MY_AGENT_IMAGE_DRAW_URL=https://draw.example.test/v1/images",
                "MY_AGENT_IMAGE_TASK_URL_TEMPLATE=https://tasks.example.test/v1/jobs",
            )
        ),
        encoding="utf-8",
    )

    settings = Settings.from_env_file(env_file)

    assert settings.image_draw_url == "https://draw.example.test/v1/images"
    assert settings.image_task_url_template == "https://tasks.example.test/v1/jobs"


def test_generate_image_rejects_reference_outside_allowed_directories(tmp_path: Path) -> None:
    external_image = tmp_path.parent / "external.png"
    external_image.write_bytes(PNG_BYTES)
    tool = ImageGenerationTool(
        workspace=tmp_path,
        api_key="test-key",
        output_dir=tmp_path / "generated-images",
    )

    result = tool.run({"prompt": "edit", "reference_images": [str(external_image)]})

    assert result == "ERROR: Reference image is outside the allowed directories."


def test_validate_public_url_rejects_loopback_address() -> None:
    try:
        validate_public_url("http://127.0.0.1:8080/image.png")
    except ValueError as exc:
        assert "not public" in str(exc)
    else:
        raise AssertionError("loopback URL must be rejected")
