"""Real examples, copied verbatim from the actual downloaded dataset
(cnamuangtoun/resume-job-description-fit train.csv), not invented."""
from app.services.dataset_sources.text_cleanup import insert_missing_header_breaks


def test_inserts_break_before_glued_summary_header():
    text = "SummaryHighly motivated Sales Associate with extensive customer service"
    result = insert_missing_header_breaks(text)
    assert result == "Summary\nHighly motivated Sales Associate with extensive customer service"


def test_inserts_break_before_glued_experience_header():
    text = "ExperienceAccountant,08/2014-05/2015Aspirus,Owen,WI"
    result = insert_missing_header_breaks(text)
    assert result.startswith("Experience\nAccountant,08/2014")


def test_matches_professional_summary_before_bare_summary_substring():
    """'Professional Summary' contains 'Summary' — the longer phrase must
    win, not leave a dangling 'Professional ' + broken 'Summary\\n...'."""
    text = "Professional SummaryCurrently working with Caterpillar"
    result = insert_missing_header_breaks(text)
    assert result == "Professional Summary\nCurrently working with Caterpillar"


def test_leaves_already_separated_headers_untouched():
    text = "Summary\nHighly motivated professional."
    assert insert_missing_header_breaks(text) == text


def test_leaves_header_word_inside_a_sentence_untouched():
    """A real header keyword that's genuinely just part of a sentence
    (lowercase, no immediate capital) shouldn't get an inserted break."""
    text = "This position requires 5 years of experience in accounting."
    assert insert_missing_header_breaks(text) == text
