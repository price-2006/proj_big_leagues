"""Structured logging (Phase 14, docs/ARCHITECTURE.md §12: "logging
redacts resume/job raw text bodies"). There was no logging anywhere in
this app before this phase — nothing to retrofit redaction into — so the
convention starts here: application code logs only structured, whitelisted
fields (ids, counts, error types, elapsed time), never a raw resume/JD
text body or a full parsed_profile/feature_vector dict.

`RedactingFilter` is defense-in-depth for that convention, not a
replacement for it: if a dict log argument ever *does* contain one of the
known-sensitive keys (a mistake, not the intended path), its value is
masked before the record is emitted rather than trusting every call site
to have gotten it right.
"""
import logging

_SENSITIVE_KEYS = {"raw_text", "parsed_profile", "chunk_text", "text", "raw_text_body"}
_REDACTED = "[REDACTED]"


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.args = _redact(record.args) if record.args else record.args
        if isinstance(record.msg, dict):
            record.msg = _redact(record.msg)
        return True


def _redact(value):
    if isinstance(value, dict):
        return {k: (_REDACTED if k in _SENSITIVE_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_redact(v) for v in value)
    return value


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
