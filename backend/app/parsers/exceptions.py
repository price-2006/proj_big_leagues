class DocumentParseError(Exception):
    """A resume/JD file could not be parsed into text.

    Raised for corrupt/malformed files and image-only PDFs with no
    extractable text. Callers (the upload endpoint in Phase 8, the dataset
    ingestion pipeline in Phase 10) catch this and surface a clean error
    instead of a raw parser-library traceback.
    """
