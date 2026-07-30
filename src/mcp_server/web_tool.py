"""web.search — wraps Serper.dev (Shopping, falling back to organic web
search) or Brave Search (organic only), returning
{title, url, snippet, price?, availability?, brand?, rating?}. brand/rating
are populated for Shopping results (merchant name, product rating when
Google has one) and always None for organic-fallback results, which have
no structured data to draw them from.

Enforces a domain allowlist and robots.txt before any *organic* result is
returned, caches responses (TTL from config), and rate-limits outbound
calls. Used when the router/planner decide the request needs current
price, availability, or "latest" info the private catalog can't answer —
or, via the Retriever's relevance check, when the private catalog simply
doesn't have the right *kind* of product.

Why Shopping first: organic web search for a product query mostly surfaces
best-seller/category listing pages ("Best Throw Pillow Covers"), not
individual products with prices — not useful for a recommendation. Serper's
Shopping endpoint returns actual product listings (title, merchant, price,
rating) instead. Its `link` field points at a Google Shopping redirect, not
the merchant's own domain, so the domain allowlist and robots.txt checks
(designed for arbitrary organic-search URLs we haven't vetted) don't apply
to it — those results come from a licensed, curated commercial product
feed via Serper's API contract, not from us crawling an arbitrary page, so
there's nothing to check them against. Organic search is still the
fallback when Shopping has no results for a query (seen in testing for
narrower/less common queries), and keeps the allowlist/robots.txt checks.
"""
import re
from typing import Optional
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


def _parse_shopping_price(text) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"[\d,]+\.?\d*", str(text))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _call_serper_shopping(query: str, num: int) -> list[dict]:
    """Real product listings (title, merchant, price, rating) via Google
    Shopping — see module docstring for why this is tried before organic
    search, and why its results skip the domain-allowlist/robots.txt checks.
    """
    if not SERPER_API_KEY:
        raise WebSearchError("SERPER_API_KEY is not set")
    resp = requests.post(
        "https://google.serper.dev/shopping",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    results = []
    for item in resp.json().get("shopping", []):
        url = item.get("link")
        if not url:
            continue
        results.append(
            {
                "title": item.get("title"),
                "url": url,
                "snippet": None,
                "price": _parse_shopping_price(item.get("price")),
                "availability": None,
                "brand": item.get("source") or None,  # merchant name, e.g. "IKEA"
                "rating": item.get("rating"),  # Shopping API omits this per-item when unavailable
            }
        )
    return results


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


def _organic_search(query: str, k: int) -> list[dict]:
    provider = _PROVIDERS.get(WEB_SEARCH_PROVIDER)
    if provider is None:
        raise WebSearchError(f"unknown WEB_SEARCH_PROVIDER: {WEB_SEARCH_PROVIDER!r}")

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
                "brand": None,  # organic search has no structured merchant/rating data
                "rating": None,
            }
        )
        if len(filtered) >= k:
            break
    return filtered


_SHOPPING_ATTEMPTS = 2


def web_search(query: str, k: int = 5) -> list[dict]:
    cached = _result_cache.get(query)
    if cached is not None:
        return cached[:k]

    if not _limiter.allow():
        raise WebSearchError("web.search rate limit exceeded, try again shortly")

    # A live HTTP failure here (bad gateway, malformed/oversized query
    # rejected by the provider, timeout, ...) is not the same kind of error
    # as a missing API key: it's exactly the situation the Answerer's
    # "empty evidence is not an error" handling already exists for. Letting
    # requests.RequestException propagate instead crashes the whole agent
    # turn — caught this via proofagent-harness's adversarial eval, where a
    # very long jailbreak-style query got Serper's organic endpoint to
    # 400, which took the entire graph down instead of just yielding zero
    # web results. Missing-API-key errors (WebSearchError, raised
    # deliberately above) are a real setup problem and still propagate.
    results: list[dict] = []
    if WEB_SEARCH_PROVIDER == "serper":
        # Serper's Shopping endpoint is flaky, not just sparse: the exact
        # same query has returned a full page of results on one call and an
        # empty list moments later, repeatedly, in testing — a second
        # attempt has consistently succeeded. Retrying here (still cheaper
        # than falling back to organic search's worse results) is
        # meaningfully different from the organic fallback below, which is
        # for queries Shopping genuinely has nothing for.
        for _ in range(_SHOPPING_ATTEMPTS):
            try:
                results = _call_serper_shopping(query, num=max(k * 2, 10))[:k]
            except requests.RequestException:
                results = []
            if results:
                break

    # Shopping has no results for some narrower/less common queries (seen in
    # testing) — organic search is the fallback, not a second-choice provider.
    if not results:
        try:
            results = _organic_search(query, k)
        except requests.RequestException:
            results = []

    _result_cache.set(query, results)
    log_event("web.search", query=query, source_urls=[r["url"] for r in results])
    return results
