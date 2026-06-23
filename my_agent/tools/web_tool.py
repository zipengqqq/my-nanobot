from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from my_agent.tools.base import ToolSchema

_DEFAULT_TIMEOUT_SECONDS = 10.0
_DEFAULT_FETCH_CHARS = 6000
_MAX_READ_BYTES = 2_000_000
_SEARCH_ENDPOINTS = (
    ("bing", "https://www.bing.com/search?", "q"),
    ("baidu", "https://www.baidu.com/s?", "wd"),
    ("sogou", "https://www.sogou.com/web?", "query"),
)


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _charset_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return "utf-8"
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    return match.group(1).strip('"') if match else "utf-8"


def _read_url(url: str, *, timeout_seconds: float) -> tuple[str, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "my_agent/0.1 (+https://example.invalid/my_agent)",
            "Accept": "text/html,text/plain;q=0.9,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read(_MAX_READ_BYTES + 1)
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl() if hasattr(response, "geturl") else url
    if len(raw) > _MAX_READ_BYTES:
        raw = raw[:_MAX_READ_BYTES]
    charset = _charset_from_content_type(content_type)
    return final_url, content_type, raw.decode(charset, errors="replace")


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = True
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = False
        if lowered in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        else:
            self.body_parts.append(text)

    @property
    def title(self) -> str:
        return _normalize_space(" ".join(self.title_parts))

    @property
    def body(self) -> str:
        return _normalize_space(" ".join(self.body_parts))


class _SearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[SearchResult] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self._in_result_block = False
        self._result_depth = 0
        self._result_title = ""
        self._result_url = ""
        self._snippet_parts: list[str] = []
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attr_map = {name.lower(): value or "" for name, value in attrs}
        classes = set(attr_map.get("class", "").split())

        if self._in_result_block:
            self._result_depth += 1
        elif lowered == "li" and "b_algo" in classes:
            self._in_result_block = True
            self._result_depth = 1
            self._result_title = ""
            self._result_url = ""
            self._snippet_parts = []

        if self._in_result_block and lowered == "p":
            self._capture_snippet = True

        if lowered != "a":
            return
        href = attr_map.get("href")
        if not href or not self._is_candidate_link(href, classes):
            return
        self._current_href = href
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)
        elif self._capture_snippet:
            self._snippet_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "a" and self._current_href is not None:
            title = _normalize_space(" ".join(self._current_text))
            url = _decode_search_href(self._current_href)
            if title and url:
                if self._in_result_block and not self._result_url:
                    self._result_title = title
                    self._result_url = url
                elif not self._in_result_block:
                    self.results.append(SearchResult(title=title, url=url))
            self._current_href = None
            self._current_text = []

        if lowered == "p":
            self._capture_snippet = False

        if self._in_result_block:
            self._result_depth -= 1
            if self._result_depth == 0:
                if self._result_title and self._result_url:
                    self.results.append(
                        SearchResult(
                            title=self._result_title,
                            url=self._result_url,
                            snippet=_normalize_space(" ".join(self._snippet_parts)),
                        )
                    )
                self._in_result_block = False
                self._result_title = ""
                self._result_url = ""
                self._snippet_parts = []
                self._capture_snippet = False

    @staticmethod
    def _is_candidate_link(href: str, classes: set[str]) -> bool:
        if "result__a" in classes:
            return True
        parsed = urllib.parse.urlparse(unescape(href))
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.netloc.lower()
        ignored_hosts = {
            "www.bing.com",
            "bing.com",
            "www.baidu.com",
            "baidu.com",
            "www.sogou.com",
            "sogou.com",
        }
        return host not in ignored_hosts


def _decode_search_href(href: str) -> str:
    href = unescape(href)
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    return href


def _search_url(endpoint: tuple[str, str, str], query: str) -> str:
    _, base_url, query_param = endpoint
    return base_url + urllib.parse.urlencode({query_param: query})


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


@dataclass(slots=True)
class WebFetchTool:
    """抓取网页内容，并把 HTML 压缩成模型更容易消费的纯文本摘要。"""

    root: Path

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="web_fetch",
            description="Fetch a URL and return a concise text version of the page.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTP or HTTPS URL to fetch."},
                    "max_chars": {
                        "type": "integer",
                        "minimum": 200,
                        "maximum": 50000,
                        "description": "Maximum response characters to return.",
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 60,
                    },
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        url = str(arguments["url"])
        max_chars = int(arguments.get("max_chars", _DEFAULT_FETCH_CHARS))
        timeout_seconds = float(arguments.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))
        final_url, content_type, content = _read_url(url, timeout_seconds=timeout_seconds)

        if "html" in content_type.lower() or "<html" in content[:200].lower():
            extractor = _HtmlTextExtractor()
            extractor.feed(content)
            title = extractor.title
            body = extractor.body
        else:
            title = ""
            body = _normalize_space(content)

        sections = [f"url: {final_url}"]
        if title:
            sections.append(f"title: {title}")
        sections.append("content:\n" + _truncate(body, max_chars))
        return "\n".join(sections)


@dataclass(slots=True)
class WebSearchTool:
    """通过 Bing / Baidu / Sogou HTML 搜索页返回少量搜索结果。"""

    root: Path

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="web_search",
            description=(
                "Search the web and return concise result titles and URLs. "
                "Use web_fetch to read a selected result."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 60,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        query = str(arguments["query"])
        max_results = int(arguments.get("max_results", 5))
        timeout_seconds = float(arguments.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))
        failures: list[str] = []

        for endpoint in _SEARCH_ENDPOINTS:
            provider_name = endpoint[0]
            try:
                _, _, content = _read_url(
                    _search_url(endpoint, query),
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                failures.append(f"{provider_name}: {exc}")
                continue

            results = self._parse_results(content, max_results)
            if results:
                return self._format_results(provider_name, results)
            failures.append(f"{provider_name}: no results parsed")

        return "No search results found\n" + "\n".join(f"- {failure}" for failure in failures)

    @staticmethod
    def _parse_results(content: str, max_results: int) -> list[SearchResult]:
        parser = _SearchResultParser()
        parser.feed(content)
        unique_results: list[SearchResult] = []
        seen_urls: set[str] = set()
        for result in parser.results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            unique_results.append(result)
            if len(unique_results) >= max_results:
                break
        return unique_results

    @staticmethod
    def _format_results(provider_name: str, results: list[SearchResult]) -> str:
        lines = [f"source: {provider_name}"]
        for index, result in enumerate(results, start=1):
            lines.append(f"{index}. {result.title}")
            lines.append(f"   {result.url}")
            if result.snippet:
                lines.append(f"   snippet: {result.snippet}")
        return "\n".join(lines)
