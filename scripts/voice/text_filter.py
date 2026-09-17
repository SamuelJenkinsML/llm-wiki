"""Text filtering for spoken output — strip code, markdown, and control length."""

import re


def strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks (```...```)."""
    return re.sub(r"```[\s\S]*?```", "", text)


def strip_inline_code(text: str) -> str:
    """Remove inline `code` spans."""
    return re.sub(r"`[^`]+`", "", text)


def strip_markdown(text: str) -> str:
    """Remove markdown formatting, keeping text content."""
    # YAML frontmatter (must be stripped first, before --- becomes horizontal rule)
    text = re.sub(r"\A---\n[\s\S]*?\n---\n?", "", text)
    # Headers: ## Title -> Title
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bold/italic: **text** or *text* or __text__ or _text_
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)
    # Images: ![alt](url) -> (remove entirely) — must come before link stripping
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Links: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Wikilinks: [[Page Name]] -> Page Name, [[Page Name|Display]] -> Display
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # Horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Bullet points: - item or * item -> item
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    # Numbered lists: 1. item -> item
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Blockquotes: > text -> text
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    # Tables: remove pipe-based table formatting
    text = re.sub(r"^\|.*\|$", "", text, flags=re.MULTILINE)
    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Split on period, exclamation, question mark followed by space or end
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def truncate(text: str, n_sentences: int = 3) -> str:
    """Keep first N sentences, append note about terminal."""
    sentences = _split_sentences(text)
    if len(sentences) <= n_sentences:
        return text
    truncated = " ".join(sentences[:n_sentences])
    return truncated + " The rest is in the terminal, sir."


def smart_filter(text: str, threshold: int = 200) -> str:
    """If text is short enough, return full; otherwise truncate."""
    # First strip code and markdown
    cleaned = strip_code_blocks(text)
    cleaned = strip_inline_code(cleaned)
    cleaned = strip_markdown(cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return ""

    word_count = len(cleaned.split())
    if word_count <= threshold:
        return cleaned
    return truncate(cleaned, n_sentences=3)


def filter_for_speech(text: str, mode: str = "smart",
                      threshold: int = 200,
                      truncate_sentences: int = 3) -> str:
    """Main entry point: filter text for spoken output based on mode."""
    if mode == "full":
        cleaned = strip_code_blocks(text)
        cleaned = strip_inline_code(cleaned)
        cleaned = strip_markdown(cleaned)
        return cleaned.strip()

    if mode == "truncate":
        cleaned = strip_code_blocks(text)
        cleaned = strip_inline_code(cleaned)
        cleaned = strip_markdown(cleaned)
        return truncate(cleaned.strip(), truncate_sentences)

    # Default: smart
    return smart_filter(text, threshold)


def extract_briefing_highlights(text: str) -> str:
    """Extract key sections from a daily briefing for spoken summary.

    Pulls: Today at a Glance, Today's Focus, Health & Training,
    and Backlog Pick of the Day.
    """
    sections_to_extract = [
        "Today at a Glance",
        "Today's Focus",
        "Health & Training",
        "Backlog Pick of the Day",
    ]

    highlights = []

    for section_name in sections_to_extract:
        # Match ## Section Name through to next ## or end
        pattern = rf"##\s+{re.escape(section_name)}\s*\n([\s\S]*?)(?=\n##\s|\Z)"
        match = re.search(pattern, text)
        if match:
            content = match.group(1).strip()
            # Clean markdown from the section content
            content = strip_code_blocks(content)
            content = strip_inline_code(content)
            content = strip_markdown(content)
            content = content.strip()
            if content:
                highlights.append(f"{section_name}. {content}")

    if not highlights:
        return ""

    return "\n\n".join(highlights)
