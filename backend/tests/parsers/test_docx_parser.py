from pathlib import Path

import pytest

from app.parsers.docx_parser import parse_docx
from app.parsers.exceptions import DocumentParseError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "resumes"


def test_resume_docx_extracts_known_strings() -> None:
    result = parse_docx((FIXTURES / "resume.docx").read_bytes())
    assert result.file_type == "docx"
    assert "Sam Rivera" in result.raw_text
    assert "sam.rivera@example.com" in result.raw_text
    assert "Go, gRPC, Terraform, GCP, Redis" in result.raw_text
    assert "University of Texas at Austin" in result.raw_text


def test_resume_docx_style_names_identify_headers() -> None:
    result = parse_docx((FIXTURES / "resume.docx").read_bytes())
    name_line = next(l for l in result.lines if l.text == "Sam Rivera")
    skills_header = next(l for l in result.lines if l.text == "Skills")
    body_line = next(l for l in result.lines if "Go, gRPC" in l.text)

    assert name_line.style_name == "Heading 1"
    assert skills_header.style_name == "Heading 2"
    assert "Heading" not in (body_line.style_name or "")


def test_corrupt_docx_raises_clean_error_not_a_crash() -> None:
    with pytest.raises(DocumentParseError):
        parse_docx((FIXTURES / "corrupt.docx").read_bytes())


def test_empty_bytes_raises_clean_error() -> None:
    with pytest.raises(DocumentParseError):
        parse_docx(b"")
