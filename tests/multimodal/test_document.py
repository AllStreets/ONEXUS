"""Tests for document processing -- text, CSV, JSON, HTML, YAML."""
from __future__ import annotations

import json

import pytest

from nexus.multimodal.document import DocumentProcessor


@pytest.fixture
def doc_processor():
    return DocumentProcessor()


class TestReadText:
    @pytest.mark.asyncio
    async def test_plain_text(self, doc_processor, tmp_path):
        txt_file = tmp_path / "hello.txt"
        txt_file.write_text("Hello, world!\nSecond line.")

        result = await doc_processor.process(str(txt_file))
        assert result.text_content == "Hello, world!\nSecond line."
        assert result.format == "txt"
        assert result.word_count == 4
        assert result.line_count == 2

    @pytest.mark.asyncio
    async def test_markdown(self, doc_processor, tmp_path):
        md_file = tmp_path / "readme.md"
        md_file.write_text("# Title\n\nSome content here.")

        result = await doc_processor.process(str(md_file))
        assert "# Title" in result.text_content
        assert result.format == "md"


class TestReadCSV:
    @pytest.mark.asyncio
    async def test_csv_parsing(self, doc_processor, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n")

        result = await doc_processor.process(str(csv_file))
        assert "2 rows" in result.text_content
        assert "3 columns" in result.text_content
        assert "Alice" in result.text_content
        assert "Bob" in result.text_content
        assert result.format == "csv"

    @pytest.mark.asyncio
    async def test_empty_csv(self, doc_processor, tmp_path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        result = await doc_processor.process(str(csv_file))
        assert "empty CSV" in result.text_content

    def test_csv_direct(self, doc_processor, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b\n1,2\n3,4\n")

        text = doc_processor.read_csv(str(csv_file))
        assert "Row 1" in text
        assert "Row 2" in text
        assert "a:" in text


class TestReadJSON:
    @pytest.mark.asyncio
    async def test_json_object(self, doc_processor, tmp_path):
        json_file = tmp_path / "data.json"
        data = {"name": "NEXUS", "version": "1.0", "features": ["a", "b", "c"]}
        json_file.write_text(json.dumps(data))

        result = await doc_processor.process(str(json_file))
        assert "NEXUS" in result.text_content
        assert "3 keys" in result.text_content
        assert result.format == "json"

    @pytest.mark.asyncio
    async def test_json_array(self, doc_processor, tmp_path):
        json_file = tmp_path / "list.json"
        json_file.write_text(json.dumps([1, 2, 3]))

        result = await doc_processor.process(str(json_file))
        assert "Array with 3 items" in result.text_content

    def test_json_direct(self, doc_processor, tmp_path):
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')

        text = doc_processor.read_json(str(json_file))
        assert "key" in text
        assert "value" in text


class TestReadHTML:
    def test_strip_tags(self, doc_processor, tmp_path):
        html_file = tmp_path / "page.html"
        html_file.write_text("<html><body><p>Hello</p><p>World</p></body></html>")

        text = doc_processor.read_html(str(html_file))
        assert "Hello" in text
        assert "World" in text
        assert "<p>" not in text

    def test_headings(self, doc_processor, tmp_path):
        html_file = tmp_path / "page.html"
        html_file.write_text("<h1>Title</h1><p>Content</p>")

        text = doc_processor.read_html(str(html_file))
        assert "Title" in text
        assert "Content" in text

    def test_strip_scripts(self, doc_processor, tmp_path):
        html_file = tmp_path / "page.html"
        html_file.write_text("<p>Keep</p><script>var x = 1;</script><p>Also keep</p>")

        text = doc_processor.read_html(str(html_file))
        assert "Keep" in text
        assert "Also keep" in text
        assert "var x" not in text

    def test_strip_styles(self, doc_processor, tmp_path):
        html_file = tmp_path / "page.html"
        html_file.write_text("<style>body { color: red; }</style><p>Text</p>")

        text = doc_processor.read_html(str(html_file))
        assert "Text" in text
        assert "color: red" not in text

    def test_html_entities(self, doc_processor, tmp_path):
        html_file = tmp_path / "page.html"
        html_file.write_text("<p>A &amp; B &lt; C</p>")

        text = doc_processor.read_html(str(html_file))
        assert "A & B < C" in text

    def test_list_items(self, doc_processor, tmp_path):
        html_file = tmp_path / "page.html"
        html_file.write_text("<ul><li>Item 1</li><li>Item 2</li></ul>")

        text = doc_processor.read_html(str(html_file))
        assert "- Item 1" in text
        assert "- Item 2" in text

    @pytest.mark.asyncio
    async def test_html_via_process(self, doc_processor, tmp_path):
        html_file = tmp_path / "page.html"
        html_file.write_text("<h1>Title</h1><p>Body text here.</p>")

        result = await doc_processor.process(str(html_file))
        assert result.format == "html"
        assert "Title" in result.text_content


class TestReadYAML:
    def test_yaml_raw_fallback(self, doc_processor, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value\nlist:\n  - item1\n  - item2\n")

        text = doc_processor.read_yaml(str(yaml_file))
        assert "key" in text
        assert "value" in text

    @pytest.mark.asyncio
    async def test_yaml_via_process(self, doc_processor, tmp_path):
        yml_file = tmp_path / "data.yml"
        yml_file.write_text("name: test\n")

        result = await doc_processor.process(str(yml_file))
        assert result.format == "yml"
        assert "name" in result.text_content


class TestReadXML:
    @pytest.mark.asyncio
    async def test_xml_via_process(self, doc_processor, tmp_path):
        xml_file = tmp_path / "data.xml"
        xml_file.write_text('<?xml version="1.0"?>\n<root><item>Hello</item></root>')

        result = await doc_processor.process(str(xml_file))
        assert result.format == "xml"
        assert "Hello" in result.text_content


class TestPDFExtraction:
    def test_basic_pdf_not_valid(self, doc_processor, tmp_path):
        pdf_file = tmp_path / "bad.pdf"
        pdf_file.write_bytes(b"not a pdf")

        text = doc_processor.extract_pdf_text(str(pdf_file))
        assert "Not a valid PDF" in text

    def test_pdf_no_text(self, doc_processor, tmp_path):
        # Valid PDF header but no text streams
        pdf_file = tmp_path / "empty.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%%EOF\n")

        text = doc_processor.extract_pdf_text(str(pdf_file))
        assert "no content" in text.lower() or "yielded no" in text.lower()


class TestDocumentProcess:
    @pytest.mark.asyncio
    async def test_file_not_found(self, doc_processor):
        with pytest.raises(FileNotFoundError):
            await doc_processor.process("/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_unsupported_format(self, doc_processor, tmp_path):
        bad_file = tmp_path / "file.exe"
        bad_file.write_text("data")
        with pytest.raises(ValueError, match="Unsupported document format"):
            await doc_processor.process(str(bad_file))

    def test_supported_formats(self, doc_processor):
        assert ".txt" in doc_processor.SUPPORTED_FORMATS
        assert ".csv" in doc_processor.SUPPORTED_FORMATS
        assert ".json" in doc_processor.SUPPORTED_FORMATS
        assert ".html" in doc_processor.SUPPORTED_FORMATS
        assert ".pdf" in doc_processor.SUPPORTED_FORMATS
        assert ".yaml" in doc_processor.SUPPORTED_FORMATS
        assert ".yml" in doc_processor.SUPPORTED_FORMATS
        assert ".md" in doc_processor.SUPPORTED_FORMATS
        assert ".xml" in doc_processor.SUPPORTED_FORMATS
