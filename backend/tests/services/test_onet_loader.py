"""Tests app/services/onet_loader.py's parsing/cleanup logic against a
small synthetic CSV matching O*NET's real column structure — no network
call in the test suite. Fetching the live file is exercised by the
manual seed procedure (backend/scripts/seed_skills.py), not pytest.
"""
from app.services.onet_loader import parse_hot_technologies

SAMPLE_CSV = """O*NET-SOC Code,Title,Workplace Example,Element ID,Element Name,Hot Technology,In Demand
11-1011.00,Chief Executives,Python,2.E.5.b,Object or component oriented development software,Y,N
11-1011.00,Chief Executives,AdSense Tracker,2.E.6.f,Data base user interface and query software,N,N
15-1252.00,Software Developers,Python,2.E.5.b,Object or component oriented development software,Y,N
15-1252.00,Software Developers,SAP software,2.E.6.a,Enterprise resource planning ERP software,Y,N
15-1252.00,Software Developers,Oracle Java,2.E.5.b,Object or component oriented development software,Y,N
15-1252.00,Software Developers,Google Angular,2.E.5.a,Web platform development software,Y,N
15-1252.00,Software Developers,IBM Terraform,2.E.6.g,Configuration management software,Y,N
"""


def test_filters_out_non_hot_technology_rows():
    names = dict(parse_hot_technologies(SAMPLE_CSV))
    assert "AdSense Tracker" not in names


def test_dedupes_technology_repeated_across_occupations():
    names = [name for name, _ in parse_hot_technologies(SAMPLE_CSV)]
    assert names.count("Python") == 1


def test_strips_trailing_software_suffix():
    names = dict(parse_hot_technologies(SAMPLE_CSV))
    assert "SAP" in names
    assert "SAP software" not in names


def test_applies_known_renames():
    names = dict(parse_hot_technologies(SAMPLE_CSV))
    assert "Java" in names
    assert "Oracle Java" not in names


def test_keeps_onet_element_name_as_category():
    names = dict(parse_hot_technologies(SAMPLE_CSV))
    assert names["Python"] == "Object or component oriented development software"


def test_renames_vendor_prefixed_entries_to_avoid_seeding_near_duplicates():
    """'Google Angular' and 'IBM Terraform' are O*NET's own naming for
    technologies already in the internal curated list (app/services/skill_seed_data.py)
    as plain 'Angular' / 'Terraform' — regression test for a real
    duplicate-skill bug this loader used to produce (see git history)."""
    names = dict(parse_hot_technologies(SAMPLE_CSV))
    assert "Angular" in names
    assert "Google Angular" not in names
    assert "Terraform" in names
    assert "IBM Terraform" not in names
