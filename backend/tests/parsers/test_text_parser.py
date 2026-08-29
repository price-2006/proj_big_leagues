import pytest

from app.parsers.exceptions import DocumentParseError
from app.parsers.text_parser import parse_text


def test_extracts_lines_and_skips_blanks() -> None:
    result = parse_text("Senior Data Engineer\n\nRequirements\n- 5+ years of experience\n   \n- Strong SQL skills")
    assert result.file_type == "text"
    assert [l.text for l in result.lines] == [
        "Senior Data Engineer",
        "Requirements",
        "- 5+ years of experience",
        "- Strong SQL skills",
    ]
    assert "Senior Data Engineer" in result.raw_text


def test_lines_carry_no_layout_metadata() -> None:
    result = parse_text("Title\nBody line")
    assert all(l.font_size is None and l.bold is False and l.style_name is None for l in result.lines)


def test_empty_text_raises_clean_error() -> None:
    with pytest.raises(DocumentParseError):
        parse_text("")


def test_whitespace_only_text_raises_clean_error() -> None:
    with pytest.raises(DocumentParseError):
        parse_text("   \n\t\n   ")
