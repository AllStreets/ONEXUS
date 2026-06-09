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

    # Log the search to chronicle so it shows in the cockpit
    try:
        kernel.chronicle.log("search", "query", {
            "q": q, "provider": provider, "hit_count": len(hits),
        })
    except Exception:
        pass

    return SearchResponse(query=q, provider=provider, hits=hits[:limit])
