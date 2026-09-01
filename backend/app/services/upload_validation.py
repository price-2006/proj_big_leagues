"""Upload validation (Phase 14, docs/ARCHITECTURE.md §12): a hard file-size
cap enforced during the read itself (not a check after buffering an
arbitrarily large body), plus magic-byte content sniffing so a file's
actual bytes have to match its claimed type — a renamed `.exe` given a
`.pdf` extension is rejected here, before either parser ever sees it.
"""
from fastapi import UploadFile

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5MB, per ARCHITECTURE.md §12
_READ_CHUNK_SIZE = 64 * 1024

# Each format's leading bytes. DOCX is OOXML-in-a-zip, so its signature is
# the generic ZIP local-file-header magic — this catches "not actually a
# zip at all" (the bulk of the renamed-file attack class); it doesn't by
# itself prove the zip contains real DOCX parts, which is what parse_docx
# (and its XXE pre-scan) verifies next.
_MAGIC_SIGNATURES: dict[str, bytes] = {
    "pdf": b"%PDF-",
    "docx": b"PK\x03\x04",
}


class UploadTooLargeError(Exception):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"File exceeds the {max_bytes} byte upload limit")
        self.max_bytes = max_bytes


class UnrecognizedFileSignatureError(Exception):
    def __init__(self, file_type: str) -> None:
        super().__init__(f"File content doesn't match the expected '{file_type}' signature")
        self.file_type = file_type


async def read_upload_within_limit(file: UploadFile, max_bytes: int = MAX_UPLOAD_SIZE_BYTES) -> bytes:
    """Reads in bounded chunks and aborts as soon as the running total
    exceeds the cap, rather than reading the whole body first and
    checking `len(data)` after — a request can never force more than
    `max_bytes + one chunk` into memory here, oversized or not."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_READ_CHUNK_SIZE):
        total += len(chunk)
        if total > max_bytes:
            raise UploadTooLargeError(max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


def verify_magic_bytes(data: bytes, file_type: str) -> None:
    signature = _MAGIC_SIGNATURES.get(file_type)
    if signature is not None and not data.startswith(signature):
        raise UnrecognizedFileSignatureError(file_type)
