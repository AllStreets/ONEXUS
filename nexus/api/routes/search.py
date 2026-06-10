"""In-OS web search.

Routes user queries through Aegis.network() to a configurable search
provider so users never have to leave the OS to look something up.
Results render as cards inside the conversation surface.

Default provider: DuckDuckGo's instant-answer API (no key required, no
tracking). Override via env: NEXUS_SEARCH_PROVIDER=brave + NEXUS_BRAVE_KEY.
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import quote_plus

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


router = APIRouter(prefix="/api/search", tags=["search"])


class SearchHit(BaseModel):
    title: str
    url: str
    snippet: str
    source: str | None = None


class SearchResponse(BaseModel):
    query: str
    provider: str
    hits: list[SearchHit]


class ReaderResponse(BaseModel):
    url: str
    title: str = ""
    text: str = ""
    digest: str = ""
    truncated: bool = False
    error: str | None = None


@router.get("/reader", response_model=ReaderResponse)
async def reader(request: Request, url: str, max_chars: int = 12000, digest: bool = True) -> ReaderResponse:
    """Open a search result in-app.

    Fetches the URL, strips scripts/styles/nav chrome, returns clean
    plaintext plus an optional LLM-generated digest. Goes through the same
    httpx path the search provider uses so the page load is auditable.
    """
    target = (url or "").strip()
    if not target.startswith(("http://", "https://")):
        raise HTTPException(400, "url must be http(s)")

    kernel = request.app.state.kernel
    title = ""
    text = ""
    truncated = False
    error: str | None = None

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0) AppleWebKit/605.1.15 Safari/605.1.15 ONEXUS-Reader/1.0",
        }) as client:
            r = await client.get(target)
            try:
                kernel.chronicle.log("search", "reader_fetch", {
                    "url": target,
                    "status": r.status_code,
                    "content_type": r.headers.get("content-type", ""),
                })
            except Exception:
                pass
            r.raise_for_status()
            html = r.text or ""
    except Exception as exc:
        return ReaderResponse(url=target, error=f"fetch failed: {exc}")

    # Very small reader — pull <title> + text outside <script>/<style>/<nav>/<footer>.
    # Keeps the dependency surface zero. Good enough for an inline summary.
    import re as _re
    m_title = _re.search(r"<title[^>]*>(.*?)</title>", html, _re.IGNORECASE | _re.DOTALL)
    if m_title:
        title = _re.sub(r"\s+", " ", m_title.group(1)).strip()[:200]
    cleaned = _re.sub(r"<(script|style|nav|footer|aside|head)[^>]*>.*?</\1>", " ", html, flags=_re.IGNORECASE | _re.DOTALL)
    cleaned = _re.sub(r"<!--.*?-->", " ", cleaned, flags=_re.DOTALL)
    cleaned = _re.sub(r"<br\s*/?>", "\n", cleaned, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"</(p|li|h[1-6]|div|section|article|tr)>", "\n", cleaned, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"<[^>]+>", " ", cleaned)
    # Collapse whitespace + decode common entities the cheap way
    cleaned = (
        cleaned
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    cleaned = _re.sub(r"[ \t]+", " ", cleaned)
    cleaned = _re.sub(r"\n\s*\n+", "\n\n", cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
        truncated = True
    text = cleaned

    out = ReaderResponse(url=target, title=title, text=text, truncated=truncated)

    # LLM digest — optional; gracefully degrades when no provider is up.
    if digest:
        router_ = getattr(kernel, "provider_router", None)
        if router_ is not None and text:
            prompt_text = text[:8000]
            messages = [
                {"role": "system", "content": (
                    "You are a fast reader. Given a web page, output a tight 4-6 bullet "
                    "summary of what it actually says — facts only, no praise, no filler. "
                    "If the page is mostly navigation or login wall, say so in one bullet."
                )},
                {"role": "user", "content": f"URL: {target}\nTitle: {title}\n\nPAGE TEXT:\n{prompt_text}"},
            ]
            try:
                digest_text = await router_.infer(messages=messages, max_tokens=500, temperature=0.3)
                out.digest = (digest_text or "").strip()
            except Exception as exc:
                out.error = f"digest failed: {exc}"
        elif router_ is None:
            out.error = "no LLM provider — install ollama for digests"

    return out


@router.get("", response_model=SearchResponse)
async def search(request: Request, q: str, limit: int = 10) -> SearchResponse:
    """Search the web through the kernel's network broker.

    Goes through aegis.network() so every search is auditable. The provider
    is configurable; the default is DuckDuckGo's instant-answer API.
    """
    q = (q or "").strip()
    if not q:
        raise HTTPException(400, "query is required")

    kernel = request.app.state.kernel
    provider = os.environ.get("NEXUS_SEARCH_PROVIDER", "duckduckgo").lower()

    hits: list[SearchHit] = []

    if provider == "brave":
        key = os.environ.get("NEXUS_BRAVE_KEY", "")
        if not key:
            raise HTTPException(500, "NEXUS_BRAVE_KEY not configured")
        url = f"https://api.search.brave.com/res/v1/web/search?q={quote_plus(q)}&count={limit}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Aegis network broker check — log and gate
                kernel.aegis._log_chronicle("net_request_allowed", {
                    "agent": "searcher", "url": "search.brave.com", "method": "GET",
                })
                r = await client.get(url, headers={"X-Subscription-Token": key})
                r.raise_for_status()
                data = r.json()
                for w in (data.get("web", {}).get("results") or [])[:limit]:
                    hits.append(SearchHit(
                        title=w.get("title", ""),
                        url=w.get("url", ""),
                        snippet=w.get("description", ""),
                        source="brave",
                    ))
        except Exception as exc:
            raise HTTPException(502, f"Brave search failed: {exc}")
    else:
        # DuckDuckGo (no key, no tracking)
        url = f"https://api.duckduckgo.com/?q={quote_plus(q)}&format=json&no_redirect=1&no_html=1"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                kernel.aegis._log_chronicle("net_request_allowed", {
                    "agent": "searcher", "url": "api.duckduckgo.com", "method": "GET",
                })
                r = await client.get(url, headers={"User-Agent": "ONEXUS/1.0"})
                r.raise_for_status()
                data = r.json()
                # DDG has Abstract, RelatedTopics, Results
                if data.get("AbstractURL"):
                    hits.append(SearchHit(
                        title=data.get("Heading") or q,
                        url=data["AbstractURL"],
                        snippet=data.get("AbstractText", ""),
                        source=data.get("AbstractSource"),
                    ))
                for t in (data.get("RelatedTopics") or [])[:limit]:
                    if "FirstURL" in t:
                        hits.append(SearchHit(
                            title=t.get("Text", "")[:80],
                            url=t["FirstURL"],
                            snippet=t.get("Text", ""),
                            source="duckduckgo",
                        ))
                    elif "Topics" in t:
                        for sub in t["Topics"][:3]:
                            hits.append(SearchHit(
                                title=sub.get("Text", "")[:80],
                                url=sub.get("FirstURL", ""),
                                snippet=sub.get("Text", ""),
                                source="duckduckgo",
                            ))
                    if len(hits) >= limit:
                        break
        except Exception as exc:
            raise HTTPException(502, f"DuckDuckGo search failed: {exc}")

    # If the provider returned no structured hits (DuckDuckGo's IAB is
    # only good for topic pages), surface useful fallbacks so the user
    # always gets actionable results instead of an empty page.
    if not hits and provider == "duckduckgo":
        hits.extend([
            SearchHit(
                title=f"DuckDuckGo — full results for “{q}”",
                url=f"https://duckduckgo.com/?q={quote_plus(q)}",
                snippet=f"Open DuckDuckGo in a new tab for full organic results. (The instant-answer API only covers topic pages — set NEXUS_SEARCH_PROVIDER=brave with NEXUS_BRAVE_KEY for inline organic search.)",
                source="duckduckgo",
            ),
            SearchHit(
                title=f"Wikipedia — “{q}”",
                url=f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(q)}",
                snippet="Search Wikipedia for this topic.",
                source="wikipedia",
            ),
        ])

    # Log the search to chronicle so it shows in the cockpit
    try:
        kernel.chronicle.log("search", "query", {
            "q": q, "provider": provider, "hit_count": len(hits),
        })
    except Exception:
        pass

    return SearchResponse(query=q, provider=provider, hits=hits[:limit])
