"""
Quarry -- web data extraction and scraping agent.
Extracts structured data from URLs, HTML snippets, and web content
using pattern matching and LLM-powered extraction.

Inspired by:
  - scrapy/scrapy (BSD 3-Clause) -- high-level web crawling framework
  - unclecode/crawl4ai (Apache 2.0) -- LLM-friendly web crawler
  - ScrapeGraphAI/Scrapegraph-ai (MIT) -- AI-powered web scraper
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class ExtractedData:
    url: str
    title: str
    links: list[str]
    headings: list[str]
    text_blocks: list[str]
    metadata: dict[str, str]


# Common metadata patterns
_META_PATTERNS: dict[str, str] = {
    "title": r'<title[^>]*>(.*?)</title>',
    "description": r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
    "author": r'<meta\s+name=["\']author["\']\s+content=["\'](.*?)["\']',
    "og_title": r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']',
    "og_description": r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']',
}


class QuarryModule(AgentModule):
    name = "quarry"
    description = "Web data extraction -- scrapes and structures data from HTML, URLs, and web content"
    version = "0.1.0"

    watch_events: list[str] = []
    coordination_targets: list[str] = []

    def __init__(self):
        self._extractions: list[ExtractedData] = []

    @staticmethod
    def extract_urls(text: str) -> list[str]:
        """Extract URLs from text."""
        urls = re.findall(r'https?://[^\s<>"\')\]]+', text)
        return list(dict.fromkeys(urls))

    @staticmethod
    def extract_links(html: str) -> list[dict[str, str]]:
        """Extract links with text from HTML."""
        links: list[dict[str, str]] = []
        for match in re.finditer(r'<a\s+[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE):
            href, text = match.group(1), re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if href and not href.startswith('#'):
                links.append({"url": href, "text": text})
        return links

    @staticmethod
    def extract_headings(html: str) -> list[dict[str, str]]:
        """Extract headings from HTML."""
        headings: list[dict[str, str]] = []
        for match in re.finditer(r'<(h[1-6])[^>]*>(.*?)</\1>', html, re.DOTALL | re.IGNORECASE):
            level, text = match.group(1), re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if text:
                headings.append({"level": level, "text": text})
        return headings

    @staticmethod
    def extract_metadata(html: str) -> dict[str, str]:
        """Extract metadata from HTML head."""
        metadata: dict[str, str] = {}
        for key, pattern in _META_PATTERNS.items():
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                metadata[key] = match.group(1).strip()
        return metadata

    @staticmethod
    def strip_tags(html: str) -> str:
        """Strip HTML tags and return clean text."""
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def extract_tables(html: str) -> list[list[list[str]]]:
        """Extract tables from HTML as nested lists."""
        tables: list[list[list[str]]] = []
        for table_match in re.finditer(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE):
            rows: list[list[str]] = []
            for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_match.group(1), re.DOTALL | re.IGNORECASE):
                cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_match.group(1), re.DOTALL | re.IGNORECASE)
                cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return tables

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        urls = self.extract_urls(message)
        has_html = bool(re.search(r'<[a-z][\s\S]*>', message, re.IGNORECASE))

        if not has_html and not urls:
            if llm:
                prompt = (
                    "The user wants to extract data from the web. "
                    "Provide a structured extraction plan for:\n\n"
                    f"{message[:3000]}\n\n"
                    "Include: target data fields, suggested selectors, extraction strategy."
                )
                try:
                    plan = await llm.complete(prompt)
                    return f"[Quarry] Extraction Plan\n\n{plan[:2000]}"
                except Exception:
                    pass
            return "[Quarry] Provide HTML content or URLs to extract data from."

        # Process HTML content
        if has_html:
            links = self.extract_links(message)
            headings = self.extract_headings(message)
            metadata = self.extract_metadata(message)
            tables = self.extract_tables(message)
            clean_text = self.strip_tags(message)

            title = metadata.get("title", metadata.get("og_title", ""))
            if not title and headings:
                title = headings[0]["text"]

            extracted = ExtractedData(
                url="", title=title,
                links=[l["url"] for l in links],
                headings=[h["text"] for h in headings],
                text_blocks=[clean_text[:500]] if clean_text else [],
                metadata=metadata,
            )
            self._extractions.append(extracted)

            lines = [f"[Quarry] Data Extracted"]
            if title:
                lines.append(f"  Title: {title}")
            if metadata:
                for k, v in metadata.items():
                    if k != "title":
                        lines.append(f"  {k}: {v[:80]}")
            if headings:
                lines.append(f"\n  Headings ({len(headings)}):")
                for h in headings[:10]:
                    lines.append(f"    {h['level']}: {h['text']}")
            if links:
                lines.append(f"\n  Links ({len(links)}):")
                for l in links[:10]:
                    lines.append(f"    {l['text'][:40]} -> {l['url'][:60]}")
            if tables:
                lines.append(f"\n  Tables: {len(tables)}")
                for i, table in enumerate(tables[:3]):
                    lines.append(f"    Table {i + 1}: {len(table)} rows x {len(table[0]) if table else 0} cols")
            if clean_text:
                lines.append(f"\n  Text preview: {clean_text[:200]}...")

            if llm:
                prompt = (
                    "Analyze the following extracted web data and provide a structured summary:\n\n"
                    f"Title: {title}\nHeadings: {', '.join(h['text'] for h in headings[:10])}\n"
                    f"Text: {clean_text[:2000]}\n\n"
                    "Provide: key topics, entities mentioned, data quality assessment."
                )
                try:
                    analysis = await llm.complete(prompt)
                    lines.append(f"\n  -- Analysis --\n  {analysis[:1000]}")
                except Exception:
                    pass

            if engram:
                try:
                    engram.episodic.store(
                        f"Web extraction: {title or 'untitled'}, "
                        f"{len(headings)} headings, {len(links)} links",
                        source=self.name,
                    )
                except Exception:
                    pass

            return "\n".join(lines)

        # URL-only mode (no fetching, just report found URLs)
        lines = [f"[Quarry] URLs Detected ({len(urls)})"]
        for u in urls[:20]:
            lines.append(f"  {u}")
        lines.append("\nProvide the HTML content for full extraction.")
        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        if self.extract_urls(message) or re.search(r'<[a-z][\s\S]*>', message, re.IGNORECASE):
            return "Quarry can extract structured data (links, headings, tables, metadata) from that HTML or URL."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        return ""
