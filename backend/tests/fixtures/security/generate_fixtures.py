"""Regenerates the fixture files in this directory — adversarial uploads
for Phase 14's security test suite (docs/ROADMAP.md: "oversized file
rejected, wrong-magic-byte file rejected, XXE payload DOCX doesn't leak
file contents"). The oversized case isn't a committed fixture (a 5MB+
binary blob doesn't belong in git history) — that one's built inline in
the test instead.

Run manually after changing this file:
    python tests/fixtures/security/generate_fixtures.py
"""
import zipfile
from io import BytesIO
from pathlib import Path

OUT_DIR = Path(__file__).parent


def build_wrong_magic_bytes(pdf_path: Path, docx_path: Path) -> None:
    """Right extension, wrong content — the exact attack class magic-byte
    sniffing exists to catch (a renamed executable/script given a
    document extension)."""
    plain_text = b"#!/bin/sh\necho this is plainly not a document\n"
    pdf_path.write_bytes(plain_text)
    docx_path.write_bytes(plain_text)


def build_xxe_payload_docx(path: Path) -> None:
    """A minimal, syntactically valid ZIP (so it passes the magic-byte
    check and DefusedZipFile can open it) containing one XML member with
    a DOCTYPE declaring an external entity that would read a local file
    if resolved. defusedxml's default parser forbids DOCTYPEs outright —
    it doesn't need to specifically detect the /etc/passwd reference —
    so this should be rejected before python-docx (which has no XXE
    hardening of its own) ever sees it."""
    xxe_xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<!DOCTYPE root [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>\n'
        b"<root>&xxe;</root>\n"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("word/document.xml", xxe_xml)
    path.write_bytes(buffer.getvalue())


if __name__ == "__main__":
    build_wrong_magic_bytes(OUT_DIR / "wrong_magic_bytes.pdf", OUT_DIR / "wrong_magic_bytes.docx")
    build_xxe_payload_docx(OUT_DIR / "xxe_payload.docx")
    print(f"Fixtures written to {OUT_DIR}")
