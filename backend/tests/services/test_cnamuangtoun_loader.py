"""No live fetch in the automated suite — a small synthetic CSV matching
the real column names and the 3 real label values confirmed against the
actual downloaded dataset (see cnamuangtoun_loader.py's module docstring).
"""
import pytest

from app.services.dataset_sources.cnamuangtoun_loader import dedupe_unique_texts, parse_fit_rows

SAMPLE_CSV = """resume_text,job_description_text,label
"Backend engineer with Python experience","Senior Backend Engineer role requiring Python","Good Fit"
"Backend engineer with Python experience","Sales Associate role at a retail store","No Fit"
"Pastry chef with 5 years experience","Head Pastry Chef at a bakery","Good Fit"
"""


def test_parses_known_label_values_to_the_documented_scale():
    rows = parse_fit_rows(SAMPLE_CSV)
    assert len(rows) == 3
    assert rows[0].label == 1.0  # Good Fit
    assert rows[1].label == 0.0  # No Fit


def test_unrecognized_label_raises_rather_than_silently_dropping():
    bad_csv = 'resume_text,job_description_text,label\n"a","b","Maybe Fit"\n'
    with pytest.raises(ValueError, match="Unrecognized label"):
        parse_fit_rows(bad_csv)


def test_resume_ref_is_stable_and_identical_for_identical_text():
    rows = parse_fit_rows(SAMPLE_CSV)
    # rows[0] and rows[1] share the same resume_text
    assert rows[0].resume_ref == rows[1].resume_ref
    assert rows[0].resume_ref != rows[2].resume_ref


def test_dedupe_unique_texts_collapses_repeated_resume():
    rows = parse_fit_rows(SAMPLE_CSV)
    resumes, jobs = dedupe_unique_texts(rows)
    assert len(resumes) == 2  # "Backend engineer..." appears twice, "Pastry chef..." once
    assert len(jobs) == 3  # all three job texts are distinct
