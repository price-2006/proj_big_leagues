"""O*NET Technology Skills loader (Phase 5) — `source='onet'` rows.

Downloads O*NET's public "Software Skills" data file directly (no account
or API key required) and keeps only the Hot-Technology-flagged rows: real,
currently-relevant named technologies, not the full ~7,700 unique entries
in the file, most of which are low-relevance occupational software (e.g.
"Blackbaud The Raiser's Edge", "AdSense Tracker") not worth seeding into a
tech-resume-focused taxonomy.

Source: O*NET 31.0 Database, U.S. Department of Labor, Employment and
Training Administration — https://www.onetcenter.org/database.html.
CC BY 4.0, confirmed at research time (docs/DATASET_STRATEGY.md §2.5);
attribution recorded in data/README.md.
"""
import csv
import io
import re
import urllib.request

ONET_SOFTWARE_SKILLS_URL = "https://www.onetcenter.org/dl_files/database/db_31_0_csv/software_skills.csv"

_TRAILING_SOFTWARE_RE = re.compile(r"\s+software$", re.IGNORECASE)

# A handful of well-known entries whose raw O*NET wording is clunky enough
# to rename outright rather than leave as the literal source string. Also
# where O*NET's vendor-prefixed naming ("Google Angular", "IBM Terraform")
# would otherwise seed a near-duplicate skill alongside the same
# technology already in the internal curated list — found by fuzzy-
# comparing every Hot Technology entry against app/services/skill_seed_data.py
# with this service's own normalize_term/_similarity (see git history for
# the check), not guessed at.
_RENAME = {
    "oracle java": "Java",
    "amazon web services aws software": "AWS",
    "structured query language sql": "SQL",
    "javascript object notation json": "JSON",
    "microsoft .net framework": ".NET",
    "jenkins ci": "Jenkins",
    "ibm terraform": "Terraform",
    "google angular": "Angular",
    "amazon dynamodb": "DynamoDB",
    "apache cassandra": "Cassandra",
}


def fetch_onet_software_skills_csv(url: str = ONET_SOFTWARE_SKILLS_URL, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")


def parse_hot_technologies(csv_text: str) -> list[tuple[str, str]]:
    """Returns deduplicated (canonical_name, category) pairs for every
    Hot-Technology-flagged row. Category is O*NET's own "Element Name"
    grouping (e.g. "Data base management system software")."""
    reader = csv.DictReader(io.StringIO(csv_text))
    seen: dict[str, str] = {}
    for row in reader:
        if row.get("Hot Technology") != "Y":
            continue
        cleaned = _clean_name(row["Workplace Example"].strip())
        seen.setdefault(cleaned, row["Element Name"].strip())
    return sorted(seen.items())


def _clean_name(raw_name: str) -> str:
    lowered = raw_name.lower()
    if lowered in _RENAME:
        return _RENAME[lowered]
    return _TRAILING_SOFTWARE_RE.sub("", raw_name).strip()


def onet_category_to_internal(element_name: str) -> str:
    return "onet:" + re.sub(r"\s+", "_", element_name.strip().lower())
