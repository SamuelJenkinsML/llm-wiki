"""Tests for voice.text_filter — text cleaning and speech preparation."""

from voice.text_filter import (
    extract_briefing_highlights,
    filter_for_speech,
    smart_filter,
    strip_code_blocks,
    strip_inline_code,
    strip_markdown,
    truncate,
)


class TestStripCodeBlocks:
    def test_removes_fenced_code(self):
        text = "Before\n```python\nprint('hello')\n```\nAfter"
        assert strip_code_blocks(text) == "Before\n\nAfter"

    def test_removes_multiple_blocks(self):
        text = "A\n```\ncode1\n```\nB\n```\ncode2\n```\nC"
        assert strip_code_blocks(text) == "A\n\nB\n\nC"

    def test_all_code_returns_empty(self):
        text = "```\nonly code\n```"
        result = strip_code_blocks(text).strip()
        assert result == ""

    def test_no_code_unchanged(self):
        text = "Just regular text."
        assert strip_code_blocks(text) == text


class TestStripInlineCode:
    def test_removes_inline_code(self):
        assert strip_inline_code("Use `foo()` here") == "Use  here"

    def test_multiple_inline(self):
        assert strip_inline_code("`a` and `b`") == " and "

    def test_no_inline_unchanged(self):
        text = "No code here"
        assert strip_inline_code(text) == text


class TestStripMarkdown:
    def test_headers(self):
        assert strip_markdown("## Hello World") == "Hello World"
        assert strip_markdown("# H1\n## H2") == "H1\nH2"

    def test_bold_italic(self):
        assert strip_markdown("**bold** and *italic*") == "bold and italic"

    def test_links(self):
        assert strip_markdown("[click here](http://example.com)") == "click here"

    def test_wikilinks(self):
        assert strip_markdown("See [[Page Name]]") == "See Page Name"
        assert strip_markdown("See [[Page|Display]]") == "See Display"

    def test_images_removed(self):
        assert strip_markdown("![alt](image.png)").strip() == ""

    def test_bullet_points(self):
        result = strip_markdown("- item one\n- item two")
        assert "item one" in result
        assert "item two" in result
        assert "- " not in result

    def test_blockquotes(self):
        assert strip_markdown("> quoted text").strip() == "quoted text"

    def test_frontmatter(self):
        text = "---\ntype: note\n---\nContent here"
        assert "type: note" not in strip_markdown(text)
        assert "Content here" in strip_markdown(text)

    def test_tables_removed(self):
        text = "| Col1 | Col2 |\n|------|------|\n| a | b |"
        result = strip_markdown(text).strip()
        assert "|" not in result


class TestTruncate:
    def test_short_text_unchanged(self):
        text = "One sentence. Two sentences."
        assert truncate(text, 3) == text

    def test_truncates_long_text(self):
        text = "First. Second. Third. Fourth. Fifth."
        result = truncate(text, 2)
        assert "First." in result
        assert "Second." in result
        assert "Third." not in result
        assert "terminal, sir" in result

    def test_exact_count_unchanged(self):
        text = "One. Two. Three."
        assert truncate(text, 3) == text


class TestSmartFilter:
    def test_short_text_full(self):
        text = "A short response with no code."
        result = smart_filter(text, threshold=200)
        assert result == text

    def test_long_text_truncated(self):
        sentences = ["Sentence number {}.".format(i) for i in range(50)]
        text = " ".join(sentences)
        result = smart_filter(text, threshold=10)
        assert "terminal, sir" in result

    def test_code_only_returns_empty(self):
        text = "```python\nprint('hello')\n```"
        assert smart_filter(text) == ""

    def test_mixed_code_and_text(self):
        text = "Here's what to do.\n```\ncode\n```\nThat's all."
        result = smart_filter(text, threshold=200)
        assert "what to do" in result
        assert "code" not in result


class TestFilterForSpeech:
    def test_full_mode(self):
        text = "**Bold** text with `code`."
        result = filter_for_speech(text, mode="full")
        assert result == "Bold text with ."

    def test_smart_mode_default(self):
        text = "Short answer."
        result = filter_for_speech(text, mode="smart")
        assert result == "Short answer."

    def test_truncate_mode(self):
        text = "One. Two. Three. Four. Five."
        result = filter_for_speech(text, mode="truncate", truncate_sentences=2)
        assert "terminal, sir" in result


class TestExtractBriefingHighlights:
    def test_extracts_sections(self):
        text = """---
type: llm-generated
---
# Good Morning

## Today at a Glance
It's Friday. Week 15.

## Today's Focus
- Finish voice integration
- Review PRs

## Calendar
- 10am standup
- 2pm design review

## Health & Training
Steps: 8000. Sleep: 7h.

## Listening — Music
Some music info here.

## Backlog Pick of the Day
Read that book about systems design.
"""
        result = extract_briefing_highlights(text)
        assert "Friday" in result
        assert "voice integration" in result
        assert "8000" in result
        assert "book about systems" in result
        # Should NOT include skipped sections
        assert "standup" not in result
        assert "music info" not in result

    def test_empty_briefing(self):
        assert extract_briefing_highlights("") == ""

    def test_missing_sections(self):
        text = "## Some Other Section\nStuff here."
        assert extract_briefing_highlights(text) == ""
