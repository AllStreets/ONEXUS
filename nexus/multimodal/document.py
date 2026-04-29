"""
DocumentProcessor -- extracts text from documents (PDF, TXT, CSV, JSON, HTML, YAML, etc.).
Uses only stdlib modules for basic processing.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import zlib
from pathlib import Path

from nexus.multimodal.models import DocumentResult


class DocumentProcessor:
    """Processes documents into structured text."""

    SUPPORTED_FORMATS = {
        ".pdf", ".txt", ".csv", ".json", ".md",
        ".html", ".htm", ".xml", ".yaml", ".yml",
    }

    async def process(self, doc_path: str) -> DocumentResult:
        """Process a document file into structured text."""
        path = Path(doc_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {doc_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported document format: {ext}")

        file_size = path.stat().st_size

        handlers = {
            ".txt": self.read_text,
            ".md": self.read_text,
            ".csv": self.read_csv,
            ".json": self.read_json,
            ".html": self.read_html,
            ".htm": self.read_html,
            ".xml": self.read_xml,
            ".yaml": self.read_yaml,
            ".yml": self.read_yaml,
            ".pdf": self.extract_pdf_text,
        }

        handler = handlers.get(ext, self.read_text)
        text_content = handler(doc_path)

        lines = text_content.split("\n")
        words = text_content.split()

        return DocumentResult(
            path=doc_path,
            format=ext.lstrip("."),
            file_size=file_size,
            text_content=text_content,
            word_count=len(words),
            line_count=len(lines),
            metadata={
                "encoding": "utf-8",
                "extension": ext,
            },
        )

    def read_text(self, path: str) -> str:
        """Read plain text files."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def read_csv(self, path: str) -> str:
        """Parse CSV into structured text representation."""
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return "(empty CSV file)"

        headers = rows[0]
        data_rows = rows[1:]

        lines = [f"CSV Table ({len(data_rows)} rows, {len(headers)} columns)"]
        lines.append("Headers: " + " | ".join(headers))
        lines.append("-" * 60)

        for i, row in enumerate(data_rows):
            # Pad row to match header count
            padded = row + [""] * (len(headers) - len(row))
            entries = [f"{h}: {v}" for h, v in zip(headers, padded)]
            lines.append(f"Row {i + 1}: {', '.join(entries)}")

        return "\n".join(lines)

    def read_json(self, path: str) -> str:
        """Parse JSON into readable text."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        def describe_structure(obj, depth: int = 0) -> str:
            indent = "  " * depth
            if isinstance(obj, dict):
                if not obj:
                    return f"{indent}(empty object)"
                parts = [f"Object with {len(obj)} keys:"]
                for key, value in obj.items():
                    if isinstance(value, (dict, list)):
                        parts.append(f"{indent}  {key}: {describe_structure(value, depth + 2)}")
                    else:
                        val_repr = repr(value)
                        if len(val_repr) > 80:
                            val_repr = val_repr[:77] + "..."
                        parts.append(f"{indent}  {key}: {val_repr}")
                return "\n".join(parts)
            elif isinstance(obj, list):
                if not obj:
                    return f"{indent}(empty array)"
                return f"Array with {len(obj)} items"
            else:
                return repr(obj)

        structure = describe_structure(data)
        pretty = json.dumps(data, indent=2, ensure_ascii=False, default=str)

        # Truncate if very large
        if len(pretty) > 10000:
            pretty = pretty[:10000] + "\n... (truncated)"

        return f"JSON Structure:\n{structure}\n\nContent:\n{pretty}"

    def read_html(self, path: str) -> str:
        """Extract text from HTML (basic, no external deps).

        Strips tags using regex, preserves structure for headings, lists, paragraphs.
        """
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()

        # Remove script and style blocks entirely
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Convert structural elements to text markers
        html = re.sub(r"<h[1-6][^>]*>", "\n## ", html, flags=re.IGNORECASE)
        html = re.sub(r"</h[1-6]>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<li[^>]*>", "\n- ", html, flags=re.IGNORECASE)
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<p[^>]*>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</p>", "\n", html, flags=re.IGNORECASE)

        # Strip all remaining tags
        text = re.sub(r"<[^>]+>", "", html)

        # Decode common HTML entities
        entities = {
            "&amp;": "&", "&lt;": "<", "&gt;": ">",
            "&quot;": '"', "&apos;": "'", "&nbsp;": " ",
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)

        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    def read_xml(self, path: str) -> str:
        """Read XML as structured text."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Strip XML tags but preserve structure via indentation
        # Simple approach: return raw XML content (it is already text)
        return content

    def read_yaml(self, path: str) -> str:
        """Parse YAML into readable text.

        Uses a basic parser since PyYAML may not be available.
        Falls back to raw text if parsing fails.
        """
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Try stdlib yaml if available
        try:
            import yaml
            data = yaml.safe_load(content)
            if isinstance(data, (dict, list)):
                return f"YAML Structure:\n{json.dumps(data, indent=2, default=str)}"
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback: return raw YAML (it is human-readable)
        return f"YAML Document:\n{content}"

    def extract_pdf_text(self, path: str) -> str:
        """Basic PDF text extraction without external dependencies.

        Parses PDF structure to find text streams. This is a best-effort extractor --
        complex PDFs with advanced encoding, CIDFont, or image-only content will need
        a full library like PyPDF2.
        """
        with open(path, "rb") as f:
            data = f.read()

        if not data.startswith(b"%PDF"):
            return "(Not a valid PDF file)"

        text_parts: list[str] = []

        # Find all stream objects and try to extract text
        stream_re = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)

        for match in stream_re.finditer(data):
            stream_data = match.group(1)

            # Try to decompress (most PDF streams are FlateDecode)
            decoded = None
            try:
                decoded = zlib.decompress(stream_data)
            except zlib.error:
                decoded = stream_data

            if decoded is None:
                continue

            # Extract text from PDF text operators
            # BT ... ET blocks contain text, Tj and TJ operators render it
            text_blocks = re.findall(rb"BT(.*?)ET", decoded, re.DOTALL)
            for block in text_blocks:
                # Handle Tj operator: (text) Tj
                tj_matches = re.findall(rb"\(([^)]*)\)", block)
                for tj in tj_matches:
                    try:
                        text = tj.decode("utf-8", errors="replace")
                        # Unescape PDF string escapes
                        text = text.replace("\\n", "\n").replace("\\r", "\r")
                        text = text.replace("\\t", "\t")
                        text = re.sub(r"\\(\d{1,3})", lambda m: chr(int(m.group(1), 8)), text)
                        text = text.replace("\\(", "(").replace("\\)", ")")
                        text = text.replace("\\\\", "\\")
                        if text.strip():
                            text_parts.append(text.strip())
                    except Exception:
                        continue

                # Handle TJ operator: [(text) kern (text)] TJ
                tj_array = re.findall(rb"\[(.*?)\]\s*TJ", block, re.DOTALL)
                for arr in tj_array:
                    strings = re.findall(rb"\(([^)]*)\)", arr)
                    combined = ""
                    for s in strings:
                        try:
                            combined += s.decode("utf-8", errors="replace")
                        except Exception:
                            continue
                    if combined.strip():
                        text_parts.append(combined.strip())

        if not text_parts:
            return "(PDF text extraction yielded no content -- the PDF may use advanced encoding or contain only images)"

        return "\n".join(text_parts)
