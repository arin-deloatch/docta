"""Text extraction and normalization utilities."""

from __future__ import annotations

import html
import re

from bs4 import Tag

from docta.utils.constants import MAX_HTML_SNIPPET_LENGTH


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    - Converts multiple spaces to single space
    - Converts multiple newlines to double newline max
    - Strips leading/trailing whitespace

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    # Replace multiple spaces with single space
    text = re.sub(r" +", " ", text)
    # Replace multiple newlines with double newline
    text = re.sub(r"\n\n+", "\n\n", text)
    # Strip leading/trailing whitespace
    return text.strip()


def extract_clean_text(elem: Tag) -> str:
    """
    Extract clean text from HTML element.

    Properly handles:
    - HTML entities (&nbsp;, &lt;, etc.)
    - Whitespace normalization

    Args:
        elem: BeautifulSoup Tag element

    Returns:
        Clean, normalized text
    """
    # Extract text with space separator
    text = elem.get_text(separator=" ", strip=True)

    # Decode HTML entities (&nbsp; -> space, etc.)
    text = html.unescape(text)

    # Normalize whitespace
    text = normalize_whitespace(text)

    return text


def truncate_html_snippet(html_snippet: str, max_length: int = MAX_HTML_SNIPPET_LENGTH) -> str:
    """
    Truncate HTML snippet to maximum length.

    Args:
        html_snippet: HTML string to truncate
        max_length: Maximum length in characters

    Returns:
        Truncated HTML with ellipsis if needed
    """
    if len(html_snippet) <= max_length:
        return html_snippet

    return html_snippet[:max_length] + "... [truncated]"
