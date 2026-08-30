from datetime import date

import pytest

from app.ml.date_utils import parse_resume_date, total_experience_years

AS_OF = date(2026, 1, 1)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Jun 2021", date(2021, 6, 1)),
        ("June 2021", date(2021, 6, 1)),
        ("Jan 2019", date(2019, 1, 1)),
        ("2021", date(2021, 1, 1)),
        ("Present", AS_OF),
        ("present", AS_OF),
        ("Current", AS_OF),
        (None, None),
        ("", None),
        ("gibberish", None),
    ],
)
def test_parse_resume_date(text, expected):
    assert parse_resume_date(text, AS_OF) == expected


def test_total_experience_years_single_ongoing_entry():
    years = total_experience_years([("Jan 2019", "Present")], AS_OF)
    assert years == pytest.approx(7.0, abs=0.05)


def test_total_experience_years_uses_span_not_sum_of_overlapping_entries():
    """Two overlapping roles shouldn't double-count the overlap — the
    span from the earliest start to the latest end (Jan 2019 -> as_of)
    is ~7 years, not ~7.5 (sum of both entries' individual durations)."""
    entries = [("Jan 2019", "Dec 2020"), ("Jun 2019", "Present")]
    years = total_experience_years(entries, AS_OF)
    assert years == pytest.approx(7.0, abs=0.05)


def test_total_experience_years_no_parseable_dates_returns_zero():
    assert total_experience_years([(None, None)], AS_OF) == 0.0
    assert total_experience_years([], AS_OF) == 0.0
