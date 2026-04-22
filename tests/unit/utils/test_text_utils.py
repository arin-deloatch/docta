"""Unit tests for docta.utils.text_utils module."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from bs4 import BeautifulSoup, Tag

from docta.utils.text_utils import (
    normalize_whitespace,
    extract_clean_text,
    truncate_html_snippet,
)


class TestNormalizeWhitespace:
    """Tests for normalize_whitespace function."""

    @pytest.mark.parametrize(
        ("input_text", "expected"),
        [
            # Single space unchanged
            ("hello world", "hello world"),
            # Multiple spaces collapsed
            ("hello    world", "hello world"),
            ("hello     world", "hello world"),
            # Multiple newlines reduced to double
            ("hello\n\n\n\nworld", "hello\n\nworld"),
            ("hello\n\n\n\n\n\nworld", "hello\n\nworld"),
            # Double newlines preserved
            ("hello\n\nworld", "hello\n\nworld"),
            # Leading/trailing whitespace stripped
            ("   hello world   ", "hello world"),
            ("\n\nhello world\n\n", "hello world"),
            # Empty and whitespace-only strings
            ("", ""),
            ("   ", ""),
            # Combined normalization (spaces only, not tabs)
            ("  hello    world\n\n\n\nfoo   bar  ", "hello world\n\nfoo bar"),
            # Single word
            ("hello", "hello"),
            ("  hello  ", "hello"),
            # Tabs are preserved (function only normalizes spaces)
            ("hello\tworld", "hello\tworld"),
            # Newlines with spaces between are not collapsed
            ("hello\n\nworld", "hello\n\nworld"),
            ("hello\n\n\nworld", "hello\n\nworld"),
        ],
    )
    def test_normalize_whitespace(self, input_text: str, expected: str) -> None:
        """Test whitespace normalization with various inputs."""
        assert normalize_whitespace(input_text) == expected


class TestExtractCleanText:
    """Tests for extract_clean_text function."""

    @pytest.fixture
    def parse_html(self) -> Callable[[str, str], Tag]:
        """Fixture to parse HTML and return the first matching element."""

        def _parse(html: str, tag: str = "p") -> Tag:
            soup = BeautifulSoup(html, "html.parser")
            elem = soup.find(tag)
            assert isinstance(elem, Tag), f"Expected Tag, got {type(elem)}"
            return elem

        return _parse

    @pytest.mark.parametrize(
        ("html", "tag", "expected_text"),
        [
            # Simple text extraction
            ("<p>Hello world</p>", "p", "Hello world"),
            ("<div>Test content</div>", "div", "Test content"),
            # Nested elements
            ("<div><p>Hello</p><p>world</p></div>", "div", "Hello world"),
            ("<div><span>A</span> <span>B</span></div>", "div", "A B"),
            # HTML entities (&nbsp; becomes \xa0, not regular space)
            ("<p>Hello&nbsp;world</p>", "p", "Hello\xa0world"),
            ("<p>&lt;test&gt;</p>", "p", "<test>"),
            ("<p>&amp;&quot;&apos;</p>", "p", "&\"'"),
            # Whitespace normalization
            ("<p>Hello    world</p>", "p", "Hello world"),
            ("<p>  Hello  world  </p>", "p", "Hello world"),
            # Empty elements
            ("<p></p>", "p", ""),
            ("<div>   </div>", "div", ""),
            # Inline formatting tags
            ("<p>Hello <strong>bold</strong> and <em>italic</em></p>", "p", "Hello bold and italic"),
            ("<p><code>code</code> and <a>link</a></p>", "p", "code and link"),
            # Complex nested structure
            (
                "<div><h1>Title</h1><p>Para 1</p><p>Para 2</p></div>",
                "div",
                "Title Para 1 Para 2",
            ),
            # Mixed content
            ("<p>Text with <br/> line break</p>", "p", "Text with line break"),
        ],
    )
    def test_extract_clean_text(self, parse_html: Callable[[str, str], Tag], html: str, tag: str, expected_text: str) -> None:
        """Test text extraction from HTML elements."""
        elem = parse_html(html, tag)
        assert extract_clean_text(elem) == expected_text

    def test_extract_preserves_text_order(self, parse_html: Callable[[str, str], Tag]) -> None:
        """Test that text extraction preserves document order."""
        html = "<div><p>First</p><p>Second</p><p>Third</p></div>"
        elem = parse_html(html, "div")
        result = extract_clean_text(elem)
        assert result.index("First") < result.index("Second")
        assert result.index("Second") < result.index("Third")


class TestTruncateHtmlSnippet:
    """Tests for truncate_html_snippet function."""

    @pytest.mark.parametrize(
        ("snippet", "max_length", "should_truncate"),
        [
            # Should NOT truncate
            ("<p>Short</p>", 100, False),
            ("x" * 50, 50, False),  # Exact length
            ("", 100, False),  # Empty string
            ("short", 1000, False),
            # Should truncate
            ("x" * 100, 50, True),
            ("<div>" + "x" * 1000 + "</div>", 100, True),
            ("Long text " * 100, 50, True),
        ],
    )
    def test_truncation_behavior(self, snippet: str, max_length: int, should_truncate: bool) -> None:
        """Test truncation occurs when expected."""
        result = truncate_html_snippet(snippet, max_length=max_length)

        if should_truncate:
            assert result.endswith("... [truncated]")
            assert len(result) == max_length + len("... [truncated]")
            assert result.startswith(snippet[:max_length])
        else:
            assert result == snippet
            assert "truncated" not in result

    @pytest.mark.parametrize(
        "max_length",
        [10, 20, 50, 100, 500],
    )
    def test_truncation_respects_max_length(self, max_length: int) -> None:
        """Test that truncation respects custom max_length values."""
        snippet = "x" * 1000
        result = truncate_html_snippet(snippet, max_length=max_length)
        assert result == "x" * max_length + "... [truncated]"

    def test_truncation_preserves_beginning(self) -> None:
        """Test that truncation preserves the start of the content."""
        important_start = "<div>IMPORTANT:</div>"
        snippet = important_start + "x" * 1000
        result = truncate_html_snippet(snippet, max_length=50)
        assert result.startswith(important_start)

    def test_empty_string_unchanged(self) -> None:
        """Test that empty strings are not modified."""
        assert truncate_html_snippet("") == ""
        assert truncate_html_snippet("", max_length=10) == ""

    @pytest.mark.parametrize(
        "snippet",
        [
            "a",
            "ab",
            "abc",
            "<p>x</p>",
        ],
    )
    def test_very_short_snippets(self, snippet: str) -> None:
        """Test that very short snippets shorter than max_length are unchanged."""
        result = truncate_html_snippet(snippet, max_length=100)
        assert result == snippet
        assert "truncated" not in result
