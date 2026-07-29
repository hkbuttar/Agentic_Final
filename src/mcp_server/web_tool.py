"""web.search — wraps Serper.dev or Brave Search, returning
{title, url, snippet, price?, availability?}.

Enforces a domain allowlist and robots.txt before any result is returned,
caches responses (TTL from config), and rate-limits outbound calls. Used
when the router/planner decide the request needs current price,
availability, or "latest" info the private catalog can't answer.
"""
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from cache import TTLCache
from config import (
    BRAVE_API_KEY,
    ROBOTS_USER_AGENT,
    SERPER_API_KEY,
    WEB_SEARCH_ALLOWED_DOMAINS,
    WEB_SEARCH_CACHE_TTL_SECONDS,
    WEB_SEARCH_PROVIDER,
    WEB_SEARCH_RATE_LIMIT_CALLS,
    WEB_SEARCH_RATE_LIMIT_PERIOD_SECONDS,
)
from log_utils import log_event
from rate_limit import RateLimiter

_REQUEST_TIMEOUT_SECONDS = 10
_ROBOTS_TIMEOUT_SECONDS = 5
_ROBOTS_CACHE_TTL_SECONDS = 3600

_result_cache = TTLCache(ttl_seconds=WEB_SEARCH_CACHE_TTL_SECONDS)
_robots_cache = TTLCache(ttl_seconds=_ROBOTS_CACHE_TTL_SECONDS)
_limiter = RateLimiter(WEB_SEARCH_RATE_LIMIT_CALLS, WEB_SEARCH_RATE_LIMIT_PERIOD_SECONDS)


class WebSearchError(RuntimeError):
    pass


def _registrable_domain(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _domain_allowed(url: str) -> bool:
    domain = _registrable_domain(url)
    return any(
        domain == allowed or domain.endswith("." + allowed)
        for allowed in WEB_SEARCH_ALLOWED_DOMAINS
    )


def _robots_allowed(url: str) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"

    parser = _robots_cache.get(origin)
    if parser is None:
        parser = RobotFileParser()
        try:
            resp = requests.get(f"{origin}/robots.txt", timeout=_ROBOTS_TIMEOUT_SECONDS)
            # A missing/unreadable robots.txt is treated as allow-all, matching
            # standard robots.txt convention (absence != disallow).
            parser.parse(resp.text.splitlines() if resp.ok else [])
        except requests.RequestException:
            parser.parse([])
        _robots_cache.set(origin, parser)

    return parser.can_fetch(ROBOTS_USER_AGENT, url)


def _call_serper(query: str, num: int) -> list[dict]:
    if not SERPER_API_KEY:
        raise WebSearchError("SERPER_API_KEY is not set")
    resp = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return [
        {"title": item.get("title"), "url": item.get("link"), "snippet": item.get("snippet")}
        for item in resp.json().get("organic", [])
    ]


def _call_brave(query: str, num: int) -> list[dict]:
    if not BRAVE_API_KEY:
        raise WebSearchError("BRAVE_API_KEY is not set")
    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
        params={"q": query, "count": num},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return [
        {"title": item.get("title"), "url": item.get("url"), "snippet": item.get("description")}
        for item in resp.json().get("web", {}).get("results", [])
    ]


_PROVIDERS = {"serper": _call_serper, "brave": _call_brave}


def web_search(query: str, k: int = 5) -> list[dict]:
    cached = _result_cache.get(query)
    if cached is not None:
        return cached[:k]

    provider = _PROVIDERS.get(WEB_SEARCH_PROVIDER)
    if provider is None:
        raise WebSearchError(f"unknown WEB_SEARCH_PROVIDER: {WEB_SEARCH_PROVIDER!r}")

    if not _limiter.allow():
        raise WebSearchError("web.search rate limit exceeded, try again shortly")

    # Over-fetch since the allowlist/robots.txt filter below will drop some.
    raw_results = provider(query, num=max(k * 3, 10))

    filtered = []
    for item in raw_results:
        url = item.get("url")
        if not url or not _domain_allowed(url) or not _robots_allowed(url):
            continue
        filtered.append(
            {
                "title": item.get("title"),
                "url": url,
                "snippet": item.get("snippet"),
                "price": None,
                "availability": None,
            }
        )
        if len(filtered) >= k:
            break

    _result_cache.set(query, filtered)
    log_event("web.search", query=query, source_urls=[r["url"] for r in filtered])
    return filtered
