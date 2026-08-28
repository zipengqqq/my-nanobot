from __future__ import annotations

import base64
import ipaddress
import json
import socket
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlparse

import httpx

from my_agent.config import logger
from my_agent.tools.base import ToolSchema

DEFAULT_DRAW_URL = "https://www.rightapi.ai/draw/v1/images/generations"
DEFAULT_TASK_URL = "https://www.rightapi.ai/v1/tasks"
_ALLOWED_ASPECT_RATIOS = {"1:1", "16:9", "9:16", "4:3"}
_ALLOWED_IMAGE_SIZES = {"1K", "2K", "4K"}
_MAX_REFERENCE_BYTES = 10 * 1024 * 1024
_MAX_OUTPUT_BYTES = 20 * 1024 * 1024


class ImageGenerationError(RuntimeError):
    """Raised when an image-generation request cannot safely complete."""


def validate_public_url(value: str) -> None:
    """Reject URLs that resolve to non-public network targets."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("remote URL must use HTTP(S) and include a hostname")

    host = parsed.hostname
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            resolved = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError("remote URL hostname could not be resolved") from exc
        addresses = [ipaddress.ip_address(item[4][0]) for item in resolved]

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("remote URL target is not public")


def _image_type(raw: bytes) -> tuple[str, str] | None:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", ".gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


class ImageGenerationTool:
    """Generate RightAPI images and store returned files under a controlled directory."""

    def __init__(
        self,
        *,
        workspace: Path,
        api_key: str,
        model: str = "gpt-image-2",
        output_dir: Path,
        draw_url: str = DEFAULT_DRAW_URL,
        task_url_template: str = DEFAULT_TASK_URL,
        timeout_seconds: float = 120.0,
        max_images_per_turn: int = 1,
        client: httpx.Client | None = None,
        poll_interval_seconds: float = 1.0,
        url_validator: Callable[[str], None] = validate_public_url,
    ) -> None:
        self.workspace = workspace.resolve()
        self.api_key = api_key
        self.model = model
        self.output_dir = output_dir.resolve()
        self.draw_url = draw_url
        self.task_url = task_url_template.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_images_per_turn = max_images_per_turn
        self.poll_interval_seconds = poll_interval_seconds
        self.url_validator = url_validator
        self._client = client or httpx.Client(timeout=15.0, follow_redirects=False)

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="generate_image",
            description=(
                "Generate or edit an image with RightAPI and save it as a local artifact. "
                "For a current pasted image attachment, the runtime automatically adds "
                "its local reference file to reference_images."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Detailed image-generation or image-editing prompt.",
                    },
                    "reference_images": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional local reference image paths from a prior result.",
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "enum": sorted(_ALLOWED_ASPECT_RATIOS),
                        "description": "Output aspect ratio.",
                    },
                    "image_size": {
                        "type": "string",
                        "enum": sorted(_ALLOWED_IMAGE_SIZES),
                        "description": "Optional output-resolution hint.",
                    },
                    "count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 4,
                        "description": "Number of images to generate.",
                    },
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        try:
            prompt = self._prompt(arguments.get("prompt"))
            count = self._count(arguments.get("count", 1))
            aspect_ratio = self._option(
                arguments.get("aspect_ratio"), _ALLOWED_ASPECT_RATIOS, "aspect_ratio"
            ) or "1:1"
            image_size = self._option(
                arguments.get("image_size"), _ALLOWED_IMAGE_SIZES, "image_size"
            )
            references = self._reference_images(arguments.get("reference_images"))
            task_id = self._submit(prompt, count, aspect_ratio, image_size, references)
            urls = self._wait_for_result(task_id)
            artifacts = [self._store_image(url, prompt, references) for url in urls[:count]]
            if not artifacts:
                raise ImageGenerationError("RightAPI completed without returning image URLs")
            return json.dumps({"artifacts": artifacts}, ensure_ascii=False)
        except (ImageGenerationError, OSError, ValueError, httpx.HTTPError) as exc:
            return f"ERROR: {exc}"

    def _submit(
        self,
        prompt: str,
        count: int,
        aspect_ratio: str,
        image_size: str | None,
        references: list[tuple[Path, bytes, str]],
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "n": count,
            "size": aspect_ratio,
            "async": True,
        }
        if image_size is not None:
            body["imageSize"] = image_size
        if references:
            body["image"] = [
                f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
                for _, raw, mime in references
            ]
        response = self._request("POST", self.draw_url, json=body)
        payload = self._json(response, "image-generation submission")
        task_id = payload.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ImageGenerationError("RightAPI submission did not return a task_id")
        logger.info("Image generation task submitted task_id=%s", task_id)
        return task_id

    def _wait_for_result(self, task_id: str) -> list[str]:
        deadline = time.monotonic() + self.timeout_seconds
        task_url = f"{self.task_url}/{quote(task_id, safe='')}"
        while True:
            response = self._request("GET", task_url)
            payload = self._json(response, "image-generation task")
            data = payload.get("data")
            if isinstance(data, list):
                urls = [item.get("url") for item in data if isinstance(item, dict)]
                completed_urls = [url for url in urls if isinstance(url, str) and url]
                if completed_urls:
                    return completed_urls
            status = payload.get("status")
            if status == "completed":
                if not isinstance(data, list):
                    raise ImageGenerationError("RightAPI completed with an invalid image result")
                urls = [item.get("url") for item in data if isinstance(item, dict)]
                return [url for url in urls if isinstance(url, str) and url]
            if status == "failed":
                error = payload.get("error")
                message = error.get("message") if isinstance(error, dict) else None
                raise ImageGenerationError(message or "RightAPI image-generation task failed")
            if status is None and isinstance(data, list):
                status = "processing"
            if status not in {"queued", "in_progress", "processing"}:
                raise ImageGenerationError(f"RightAPI returned unexpected task status: {status!r}")
            if time.monotonic() >= deadline:
                raise ImageGenerationError(
                    f"RightAPI image-generation task timed out after {self.timeout_seconds:g} seconds"
                )
            time.sleep(self.poll_interval_seconds)

    def _store_image(
        self,
        url: str,
        prompt: str,
        references: list[tuple[Path, bytes, str]],
    ) -> dict[str, Any]:
        raw = self._download_image(url)
        image_info = _image_type(raw)
        if image_info is None:
            raise ImageGenerationError("RightAPI returned an unsupported image format")
        mime_type, extension = image_info
        timestamp = datetime.now().astimezone()
        output_dir = self.output_dir / timestamp.strftime("%Y-%m-%d")
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_id = f"img_{uuid.uuid4().hex[:12]}"
        path = output_dir / f"{artifact_id}{extension}"
        path.write_bytes(raw)
        artifact = {
            "id": artifact_id,
            "path": self._display_path(path),
            "mime_type": mime_type,
            "model": self.model,
            "prompt": prompt,
            "source_images": [self._display_path(reference[0]) for reference in references],
        }
        path.with_suffix(".json").write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return artifact

    def _download_image(self, url: str) -> bytes:
        self.url_validator(url)
        try:
            with self._client.stream("GET", url, follow_redirects=False) as response:
                self._require_success(response, "image download")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > _MAX_OUTPUT_BYTES:
                        raise ImageGenerationError("generated image exceeds the 20 MiB limit")
                    chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise ImageGenerationError(f"generated image download failed: {exc}") from exc
        return b"".join(chunks)

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.url_validator(url)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = self._client.request(method, url, headers=headers, follow_redirects=False, **kwargs)
        except httpx.HTTPError as exc:
            raise ImageGenerationError(f"RightAPI request failed: {exc}") from exc
        self._require_success(response, "RightAPI request")
        return response

    @staticmethod
    def _require_success(response: httpx.Response, operation: str) -> None:
        if response.is_redirect:
            raise ImageGenerationError(f"{operation} redirected to another URL")
        if response.is_success:
            return
        detail = response.text[:500].strip()
        raise ImageGenerationError(
            f"{operation} failed with HTTP {response.status_code}" + (f": {detail}" if detail else "")
        )

    @staticmethod
    def _json(response: httpx.Response, operation: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ImageGenerationError(f"{operation} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ImageGenerationError(f"{operation} returned an invalid response")
        return payload

    def _reference_images(self, value: Any) -> list[tuple[Path, bytes, str]]:
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ImageGenerationError("reference_images must be an array of local file paths")
        references: list[tuple[Path, bytes, str]] = []
        for raw_path in value:
            path = self._resolve_reference_path(raw_path)
            raw = path.read_bytes()
            if len(raw) > _MAX_REFERENCE_BYTES:
                raise ImageGenerationError("reference image exceeds the 10 MiB limit")
            image_info = _image_type(raw)
            if image_info is None:
                raise ImageGenerationError("reference image is not a supported image format")
            references.append((path, raw, image_info[0]))
        return references

    def _resolve_reference_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        candidate = path.resolve() if path.is_absolute() else (self.workspace / path).resolve()
        if not candidate.is_file():
            raise ImageGenerationError("reference image does not exist or is not a file")
        for root in (self.workspace, self.output_dir):
            try:
                candidate.relative_to(root)
                return candidate
            except ValueError:
                continue
        raise ImageGenerationError("Reference image is outside the allowed directories.")

    def _display_path(self, path: Path) -> str:
        return str(path.resolve())

    def _prompt(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ImageGenerationError("prompt must be a non-empty string")
        prompt = value.strip()
        if len(prompt) > 12_000:
            raise ImageGenerationError("prompt exceeds the 12000 character limit")
        return prompt

    def _count(self, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ImageGenerationError("count must be a positive integer")
        if value > self.max_images_per_turn:
            raise ImageGenerationError(
                f"count exceeds the configured maximum of {self.max_images_per_turn}"
            )
        return value

    @staticmethod
    def _option(value: Any, allowed: set[str], name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or value not in allowed:
            choices = ", ".join(sorted(allowed))
            raise ImageGenerationError(f"{name} must be one of: {choices}")
        return value
