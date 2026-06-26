"""외부 웹 검색 — Tavily(선택) · DuckDuckGo Instant(폴백)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from app.config import settings

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebHit:
    title: str
    url: str
    snippet: str
    source: str  # tavily | duckduckgo


def web_search_configured() -> bool:
    return bool((settings.tavily_api_key or "").strip())


def _http_json(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20,
) -> dict | list | None:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(
        url,
        data=data,
        headers=headers or {},
        method=method,
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        _LOG.warning("web search HTTP failed (%s): %s", url[:60], exc)
        return None


def _search_tavily(query: str, *, max_results: int) -> list[WebHit]:
    key = (settings.tavily_api_key or "").strip()
    if not key:
        return []
    payload = {
        "api_key": key,
        "query": query,
        "max_results": max(1, min(max_results, 8)),
        "search_depth": "basic",
        "include_answer": False,
    }
    data = _http_json(
        "https://api.tavily.com/search",
        method="POST",
        body=payload,
        headers={"Content-Type": "application/json"},
    )
    if not isinstance(data, dict):
        return []
    hits: list[WebHit] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        title = str(item.get("title") or url).strip()
        snippet = str(item.get("content") or "").strip()
        hits.append(WebHit(title=title, url=url, snippet=snippet[:400], source="tavily"))
    return hits


def _flatten_ddg_topics(topics: list, out: list[WebHit], *, limit: int) -> None:
    for topic in topics:
        if len(out) >= limit:
            return
        if not isinstance(topic, dict):
            continue
        if "Topics" in topic:
            _flatten_ddg_topics(topic.get("Topics") or [], out, limit=limit)
            continue
        url = str(topic.get("FirstURL") or "").strip()
        text = str(topic.get("Text") or "").strip()
        if not url.startswith("http") or not text:
            continue
        title = text.split(" - ", 1)[0][:120]
        out.append(WebHit(title=title, url=url, snippet=text[:400], source="duckduckgo"))


def _search_duckduckgo(query: str, *, max_results: int) -> list[WebHit]:
    url = (
        "https://api.duckduckgo.com/?"
        f"q={quote_plus(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
    )
    data = _http_json(url)
    if not isinstance(data, dict):
        return []

    hits: list[WebHit] = []
    abstract = str(data.get("AbstractText") or "").strip()
    abstract_url = str(data.get("AbstractURL") or "").strip()
    if abstract and abstract_url.startswith("http"):
        title = str(data.get("Heading") or abstract[:80]).strip()
        hits.append(
            WebHit(title=title, url=abstract_url, snippet=abstract[:400], source="duckduckgo")
        )

    _flatten_ddg_topics(data.get("RelatedTopics") or [], hits, limit=max_results)
    return hits[:max_results]


def web_search(query: str, *, max_results: int = 5) -> list[WebHit]:
    """Tavily 키가 있으면 우선, 없으면 DuckDuckGo Instant."""
    q = re.sub(r"\s+", " ", (query or "").strip())
    if not q:
        return []

    if web_search_configured():
        hits = _search_tavily(q, max_results=max_results)
        if hits:
            return hits[:max_results]

    return _search_duckduckgo(q, max_results=max_results)
