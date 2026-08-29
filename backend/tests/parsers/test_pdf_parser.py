from pathlib import Path

import pytest

from app.parsers.exceptions import DocumentParseError
from app.parsers.pdf_parser import parse_pdf

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "resumes"


def test_single_column_extracts_known_strings() -> None:
    result = parse_pdf((FIXTURES / "single_column.pdf").read_bytes())
    assert result.file_type == "pdf"
    assert result.page_count == 1
    assert "Jordan Ellis" in result.raw_text
    assert "jordan.ellis@example.com" in result.raw_text
    assert "Python, SQL, Docker, FastAPI, PyTorch" in result.raw_text
    assert "University of Washington" in result.raw_text


def test_single_column_layout_metadata_distinguishes_headers() -> None:
    result = parse_pdf((FIXTURES / "single_column.pdf").read_bytes())
    name_line = next(l for l in result.lines if l.text == "Jordan Ellis")
    skills_header = next(l for l in result.lines if l.text == "TECHNICAL SKILLS")
    body_line = next(l for l in result.lines if "Python, SQL" in l.text)

    assert name_line.font_size > body_line.font_size
    assert skills_header.bold is True
    assert body_line.bold is False
    assert name_line.page_number == 1
    assert name_line.bbox is not None


def test_two_column_extracts_both_columns() -> None:
    result = parse_pdf((FIXTURES / "two_column.pdf").read_bytes())
    assert "Taylor Morgan" in result.raw_text
    assert "Java, Spring Boot, Kubernetes" in result.raw_text  # left column
    assert "Backend Engineer, Globex Inc -- Mar 2020 to Present" in result.raw_text  # right column
    assert "M.S. Software Engineering" in result.raw_text


def test_corrupt_pdf_raises_clean_error_not_a_crash() -> None:
    with pytest.raises(DocumentParseError):
        parse_pdf((FIXTURES / "corrupt.pdf").read_bytes())


def test_empty_bytes_raises_clean_error() -> None:
    with pytest.raises(DocumentParseError):
        parse_pdf(b"")
