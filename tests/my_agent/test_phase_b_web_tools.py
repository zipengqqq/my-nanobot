from __future__ import annotations

from pathlib import Path

from my_agent.app import build_app
from my_agent.tools.web_tool import WebFetchTool, WebSearchTool


def test_web_fetch_reads_and_summarizes_http_page(tmp_path: Path, monkeypatch) -> None:
    url = "https://example.com/doc"
    page_html = (
        "<html><head><title>Local Doc</title></head>"
        "<body><h1>Hello Web</h1><p>Fetched content.</p></body></html>"
    ).encode("utf-8")

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int = -1) -> bytes:
            return page_html

        def geturl(self) -> str:
            return url

    def fake_urlopen(request, timeout: float = 0):
        assert request.full_url == url
        assert timeout == 10.0
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = WebFetchTool(root=tmp_path).run({"url": url})

    assert result == "url: " + url + "\ntitle: Local Doc\ncontent:\nHello Web Fetched content."


def test_web_search_uses_bing_as_primary_search_backend(tmp_path: Path, monkeypatch) -> None:
    search_html = """
    <html><body>
      <a class="result__a" href="https://example.com/first">First Result</a>
      <a class="result__a" href="https://example.com/second">Second Result</a>
    </body></html>
    """.encode("utf-8")

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int = -1) -> bytes:
            return search_html

    def fake_urlopen(request, timeout: float = 0):
        assert "duckduckgo.com" not in request.full_url
        assert "bing.com/search" in request.full_url
        assert "q=nanobot+agent" in request.full_url
        assert timeout == 10.0
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = WebSearchTool(root=tmp_path).run({"query": "nanobot agent", "max_results": 2})

    assert result == (
        "source: bing\n"
        "1. First Result\n"
        "   https://example.com/first\n"
        "2. Second Result\n"
        "   https://example.com/second"
    )


def test_web_search_falls_back_to_baidu_when_bing_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bing_html = """
    <html><body>
      <li class="b_algo">
        <h2><a href="https://example.com/bing">Bing Result</a></h2>
      </li>
    </body></html>
    """.encode("utf-8")
    requested_urls: list[str] = []

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int = -1) -> bytes:
            return bing_html

    def fake_urlopen(request, timeout: float = 0):
        requested_urls.append(request.full_url)
        assert "duckduckgo.com" not in request.full_url
        if "bing.com/search" in request.full_url:
            raise TimeoutError("timed out")
        assert "baidu.com/s" in request.full_url
        assert "wd=nanobot+agent" in request.full_url
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = WebSearchTool(root=tmp_path).run({"query": "nanobot agent", "max_results": 1})

    assert requested_urls == [
        "https://www.bing.com/search?q=nanobot+agent",
        "https://www.baidu.com/s?wd=nanobot+agent",
    ]
    assert result == "source: baidu\n1. Bing Result\n   https://example.com/bing"


def test_web_search_returns_snippets_and_filters_search_engine_links(
    tmp_path: Path,
    monkeypatch,
) -> None:
    search_html = """
    <html><body>
      <a href="https://www.bing.com/search?q=Trump">Bing navigation</a>
      <li class="b_algo">
        <h2><a href="https://www.reuters.com/world/us/trump-policy">Trump policy latest</a></h2>
        <p>Reuters summary of the latest policy move.</p>
      </li>
    </body></html>
    """.encode("utf-8")

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int = -1) -> bytes:
            return search_html

    def fake_urlopen(request, timeout: float = 0):
        assert "bing.com/search" in request.full_url
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = WebSearchTool(root=tmp_path).run({"query": "Trump policy", "max_results": 1})

    assert result == (
        "source: bing\n"
        "1. Trump policy latest\n"
        "   https://www.reuters.com/world/us/trump-policy\n"
        "   snippet: Reuters summary of the latest policy move."
    )


def test_build_app_registers_web_default_tools(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://example.com/v1",
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=gpt-4o-mini",
                "MY_AGENT_SESSION_ID=lesson",
                "MY_AGENT_HISTORY_LIMIT=12",
            ]
        ),
        encoding="utf-8",
    )

    app_state = build_app(env_file=env_file)
    tool_names = [
        schema["function"]["name"]
        for schema in app_state.loop.runner.tool_registry.list_schemas()
    ]

    assert tool_names == [
        "read_file",
        "list_dir",
        "exec",
        "write_file",
        "edit_file",
        "find_files",
        "grep",
        "apply_patch",
        "start_exec_session",
        "write_stdin",
        "list_exec_sessions",
        "web_search",
        "web_fetch",
    ]
