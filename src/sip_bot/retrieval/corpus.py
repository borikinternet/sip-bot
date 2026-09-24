"""Strict, typed input boundary for versioned local RAG corpus packages."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from .contracts import (
    CHUNKING_POLICY_VERSION,
    CORPUS_SCHEMA_VERSION,
    CorpusChunk,
    CorpusDocument,
    CorpusIngestionResult,
    CorpusManifest,
    CorpusSource,
    CorpusValidationIssue,
    CorpusValidationReport,
)


_MANIFEST_REQUIRED = frozenset(
    {"schema_version", "corpus_id", "corpus_version", "title", "language", "license", "sources"}
)
_SOURCE_REQUIRED = frozenset(
    {
        "source_id",
        "file",
        "title",
        "license",
        "attribution",
        "owner",
        "version",
        "effective_date",
        "priority",
        "topics",
        "audiences",
    }
)
_SOURCE_OPTIONAL = frozenset({"url", "origin"})
_STABLE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_LANGUAGE_TAG = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CorpusValidationError(ValueError):
    """Raised when a corpus package cannot cross the strict typed boundary."""

    def __init__(self, report: CorpusValidationReport) -> None:
        self.report = report
        summary = "; ".join(f"{item.code}@{item.location}" for item in report.errors)
        super().__init__(f"invalid corpus package: {summary}")


class _DuplicateJsonKeyError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _issue(
    errors: list[CorpusValidationIssue],
    code: str,
    message: str,
    location: str,
    source_id: str | None = None,
) -> None:
    errors.append(CorpusValidationIssue(code, message, location, source_id))


def _required_text(
    value: object,
    *,
    field: str,
    location: str,
    errors: list[CorpusValidationIssue],
    source_id: str | None = None,
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        _issue(errors, "invalid_field", f"{field} must be a non-empty string", location, source_id)
        return None
    if value != value.strip():
        _issue(errors, "non_canonical_field", f"{field} must not have surrounding whitespace", location, source_id)
        return None
    return value


def _string_tuple(
    value: object,
    *,
    field: str,
    location: str,
    errors: list[CorpusValidationIssue],
    source_id: str | None,
) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not value:
        _issue(errors, "invalid_field", f"{field} must be a non-empty array of strings", location, source_id)
        return None
    items: list[str] = []
    for position, item in enumerate(value):
        parsed = _required_text(
            item,
            field=f"{field}[{position}]",
            location=f"{location}.{field}[{position}]",
            errors=errors,
            source_id=source_id,
        )
        if parsed is not None:
            items.append(parsed)
    folded = [item.casefold() for item in items]
    if len(folded) != len(set(folded)):
        _issue(errors, "duplicate_metadata", f"{field} values must be unique", f"{location}.{field}", source_id)
        return None
    return tuple(sorted(items, key=lambda item: (item.casefold(), item))) if len(items) == len(value) else None


def _safe_relative_markdown(
    raw: object,
    *,
    root: Path,
    location: str,
    errors: list[CorpusValidationIssue],
    source_id: str | None,
) -> PurePosixPath | None:
    value = _required_text(
        raw, field="file", location=f"{location}.file", errors=errors, source_id=source_id
    )
    if value is None:
        return None
    if "\\" in value:
        _issue(errors, "invalid_path", "file must use relative POSIX separators", f"{location}.file", source_id)
        return None
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        _issue(errors, "unsafe_path", "file must be a confined relative path", f"{location}.file", source_id)
        return None
    if ":" in relative.parts[0] or relative.suffix != ".md":
        _issue(errors, "invalid_path", "file must be a relative .md path", f"{location}.file", source_id)
        return None
    resolved_root = root.resolve()
    resolved_file = (root / Path(*relative.parts)).resolve()
    try:
        resolved_file.relative_to(resolved_root)
    except ValueError:
        _issue(errors, "unsafe_path", "file resolves outside the corpus root", f"{location}.file", source_id)
        return None
    return relative


def _parse_source(
    value: object,
    *,
    position: int,
    root: Path,
    errors: list[CorpusValidationIssue],
) -> CorpusSource | None:
    location = f"manifest.sources[{position}]"
    if not isinstance(value, Mapping):
        _issue(errors, "invalid_source", "source must be a JSON object", location)
        return None
    keys = set(value)
    for field in sorted(_SOURCE_REQUIRED - keys):
        _issue(errors, "missing_field", f"missing required field: {field}", location)
    for field in sorted(keys - _SOURCE_REQUIRED - _SOURCE_OPTIONAL):
        _issue(errors, "unknown_field", f"unknown source field: {field}", f"{location}.{field}")
    if _SOURCE_REQUIRED - keys or keys - _SOURCE_REQUIRED - _SOURCE_OPTIONAL:
        return None

    source_id = _required_text(
        value["source_id"], field="source_id", location=f"{location}.source_id", errors=errors
    )
    if source_id is not None and not _STABLE_ID.fullmatch(source_id):
        _issue(
            errors,
            "invalid_source_id",
            "source_id must be lowercase ASCII words separated by hyphens",
            f"{location}.source_id",
            source_id,
        )
        source_id = None

    relative = _safe_relative_markdown(
        value["file"], root=root, location=location, errors=errors, source_id=source_id
    )
    parsed: dict[str, str | None] = {}
    for field in ("title", "license", "attribution", "owner", "version"):
        parsed[field] = _required_text(
            value[field], field=field, location=f"{location}.{field}", errors=errors, source_id=source_id
        )

    raw_url = value.get("url", "")
    if raw_url is None:
        raw_url = ""
    if not isinstance(raw_url, str) or raw_url != raw_url.strip():
        _issue(errors, "invalid_field", "url must be a string without surrounding whitespace", f"{location}.url", source_id)
        url = None
    else:
        url = raw_url
        if url:
            parsed_url = urlparse(url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                _issue(errors, "invalid_url", "url must be an absolute HTTP(S) URL", f"{location}.url", source_id)
                url = None

    raw_origin = value.get("origin", "")
    if raw_origin is None:
        raw_origin = ""
    if not isinstance(raw_origin, str) or raw_origin != raw_origin.strip():
        _issue(
            errors,
            "invalid_field",
            "origin must be a string without surrounding whitespace",
            f"{location}.origin",
            source_id,
        )
        origin = None
    else:
        origin = raw_origin
    if not url and not origin:
        _issue(errors, "missing_provenance", "at least one of url or origin is required", location, source_id)

    raw_date = value["effective_date"]
    effective_date: date | None = None
    if not isinstance(raw_date, str) or not _ISO_DATE.fullmatch(raw_date):
        _issue(errors, "invalid_date", "effective_date must use YYYY-MM-DD", f"{location}.effective_date", source_id)
    else:
        try:
            effective_date = date.fromisoformat(raw_date)
        except ValueError:
            _issue(errors, "invalid_date", "effective_date is not a calendar date", f"{location}.effective_date", source_id)

    raw_priority = value["priority"]
    if isinstance(raw_priority, bool) or not isinstance(raw_priority, int) or not 0 <= raw_priority <= 1000:
        _issue(errors, "invalid_priority", "priority must be an integer from 0 to 1000", f"{location}.priority", source_id)
        priority = None
    else:
        priority = raw_priority

    topics = _string_tuple(
        value["topics"], field="topics", location=location, errors=errors, source_id=source_id
    )
    audiences = _string_tuple(
        value["audiences"], field="audiences", location=location, errors=errors, source_id=source_id
    )

    if any(item is None for item in (*parsed.values(), source_id, relative, url, origin, effective_date, priority, topics, audiences)):
        return None
    return CorpusSource(
        source_id=source_id,
        title=parsed["title"],
        url=url,
        license=parsed["license"],
        attribution=parsed["attribution"],
        file=relative.as_posix(),
        origin=origin,
        owner=parsed["owner"],
        version=parsed["version"],
        effective_date=effective_date,
        priority=priority,
        topics=topics,
        audiences=audiences,
    )


def _parse_manifest(
    raw: object, *, root: Path, errors: list[CorpusValidationIssue]
) -> CorpusManifest | None:
    if not isinstance(raw, Mapping):
        _issue(errors, "invalid_manifest", "manifest root must be a JSON object", "manifest")
        return None
    keys = set(raw)
    for field in sorted(_MANIFEST_REQUIRED - keys):
        _issue(errors, "missing_field", f"missing required field: {field}", "manifest")
    for field in sorted(keys - _MANIFEST_REQUIRED):
        _issue(errors, "unknown_field", f"unknown manifest field: {field}", f"manifest.{field}")
    if _MANIFEST_REQUIRED - keys or keys - _MANIFEST_REQUIRED:
        return None

    schema_version = _required_text(
        raw["schema_version"], field="schema_version", location="manifest.schema_version", errors=errors
    )
    if schema_version is not None and schema_version != CORPUS_SCHEMA_VERSION:
        _issue(
            errors,
            "unsupported_schema",
            f"schema_version must be {CORPUS_SCHEMA_VERSION}",
            "manifest.schema_version",
        )
        schema_version = None

    corpus_id = _required_text(raw["corpus_id"], field="corpus_id", location="manifest.corpus_id", errors=errors)
    if corpus_id is not None and not _STABLE_ID.fullmatch(corpus_id):
        _issue(
            errors,
            "invalid_corpus_id",
            "corpus_id must be lowercase ASCII words separated by hyphens",
            "manifest.corpus_id",
        )
        corpus_id = None
    corpus_version = _required_text(
        raw["corpus_version"], field="corpus_version", location="manifest.corpus_version", errors=errors
    )
    title = _required_text(raw["title"], field="title", location="manifest.title", errors=errors)
    language = _required_text(raw["language"], field="language", location="manifest.language", errors=errors)
    if language is not None and not _LANGUAGE_TAG.fullmatch(language):
        _issue(errors, "invalid_language", "language must be a BCP-47-like tag", "manifest.language")
        language = None
    license_name = _required_text(raw["license"], field="license", location="manifest.license", errors=errors)

    raw_sources = raw["sources"]
    if not isinstance(raw_sources, list) or not raw_sources:
        _issue(errors, "invalid_sources", "sources must be a non-empty array", "manifest.sources")
        sources: list[CorpusSource] = []
    else:
        sources = [
            source
            for position, item in enumerate(raw_sources)
            if (source := _parse_source(item, position=position, root=root, errors=errors)) is not None
        ]

    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    for source in sources:
        if source.source_id in seen_ids:
            _issue(errors, "duplicate_source_id", "source_id must be unique", "manifest.sources", source.source_id)
        seen_ids.add(source.source_id)
        if source.file in seen_files:
            _issue(errors, "duplicate_file", "file must be unique", "manifest.sources", source.source_id)
        seen_files.add(source.file)

    if any(item is None for item in (schema_version, corpus_id, corpus_version, title, language, license_name)):
        return None
    return CorpusManifest(
        schema_version=schema_version,
        corpus_id=corpus_id,
        corpus_version=corpus_version,
        title=title,
        language=language,
        license=license_name,
        sources=tuple(sorted(sources, key=lambda source: source.source_id)),
    )


def _read_documents(
    root: Path, manifest: CorpusManifest, errors: list[CorpusValidationIssue]
) -> tuple[CorpusDocument, ...]:
    documents: list[CorpusDocument] = []
    for source in manifest.sources:
        relative = PurePosixPath(source.file)
        path = root / Path(*relative.parts)
        try:
            data = path.read_bytes()
        except OSError as exc:
            _issue(errors, "document_unreadable", str(exc), f"source:{source.source_id}.file", source.source_id)
            continue
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            _issue(
                errors,
                "invalid_utf8",
                f"document is not strict UTF-8: {exc}",
                f"source:{source.source_id}.file",
                source.source_id,
            )
            continue
        if text.startswith("\ufeff"):
            _issue(errors, "utf8_bom", "UTF-8 BOM is not allowed", f"source:{source.source_id}.file", source.source_id)
            continue
        if "\x00" in text:
            _issue(errors, "invalid_document", "document contains NUL", f"source:{source.source_id}.file", source.source_id)
            continue
        if not text.strip():
            _issue(errors, "empty_document", "document must contain non-whitespace text", f"source:{source.source_id}.file", source.source_id)
            continue
        documents.append(
            CorpusDocument(
                source=source,
                relative_path=relative,
                text=text,
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    return tuple(documents)


class CorpusPackage:
    """Validated immutable package consumed by later ingestion/build plans."""

    def __init__(self, root: Path, manifest: CorpusManifest, documents: tuple[CorpusDocument, ...]) -> None:
        self.root = root
        self.manifest = manifest
        self.documents = documents

    @classmethod
    def validate(cls, root: Path | str) -> CorpusValidationReport:
        package_root = Path(root)
        errors: list[CorpusValidationIssue] = []
        manifest_path = package_root / "manifest.json"
        manifest: CorpusManifest | None = None
        documents: tuple[CorpusDocument, ...] = ()
        try:
            data = manifest_path.read_bytes()
        except OSError as exc:
            _issue(errors, "manifest_unreadable", str(exc), "manifest.json")
        else:
            try:
                text = data.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                _issue(errors, "invalid_utf8", f"manifest is not strict UTF-8: {exc}", "manifest.json")
            else:
                try:
                    raw = json.loads(
                        text,
                        object_pairs_hook=_strict_object,
                        parse_constant=_reject_json_constant,
                    )
                except (json.JSONDecodeError, _DuplicateJsonKeyError, ValueError) as exc:
                    _issue(errors, "invalid_json", str(exc), "manifest.json")
                else:
                    manifest = _parse_manifest(raw, root=package_root, errors=errors)
                    if manifest is not None:
                        documents = _read_documents(package_root, manifest, errors)
        return CorpusValidationReport(
            root=str(package_root.resolve()),
            manifest=manifest,
            documents=documents,
            errors=tuple(errors),
        )

    @classmethod
    def load(cls, root: Path | str) -> "CorpusPackage":
        report = cls.validate(root)
        if not report.valid:
            raise CorpusValidationError(report)
        assert report.manifest is not None
        return cls(Path(root).resolve(), report.manifest, report.documents)


def validate_corpus_package(root: Path | str) -> CorpusValidationReport:
    """Return a machine-readable report without allowing invalid input onward."""

    return CorpusPackage.validate(root)


class CorpusNormalizer:
    """Canonicalize Markdown layout without rewriting source wording."""

    @staticmethod
    def normalize(text: str) -> str:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        normalized: list[str] = []
        blank = False
        for line in lines:
            clean = line.rstrip()
            if not clean:
                if normalized and not blank:
                    normalized.append("")
                blank = True
                continue
            normalized.append(clean)
            blank = False
        while normalized and not normalized[-1]:
            normalized.pop()
        return "\n".join(normalized) + "\n"


class CorpusChunker:
    """Deterministic Markdown heading/paragraph chunker for the compact MVP."""

    def __init__(self, *, max_chars: int = 1200) -> None:
        if max_chars < 200:
            raise ValueError("max_chars must be at least 200")
        self.max_chars = max_chars

    def chunk(self, document: CorpusDocument) -> tuple[CorpusChunk, ...]:
        normalized = CorpusNormalizer.normalize(document.text)
        blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
        heading = ""
        payloads: list[str] = []
        for block in blocks:
            if all(line.lstrip().startswith("#") for line in block.splitlines()):
                heading = " ".join(line.lstrip("# ") for line in block.splitlines()).strip()
                continue
            body = " ".join(part.strip() for part in block.splitlines() if part.strip())
            prefix = f"{heading}\n" if heading else ""
            payloads.extend(self._split_long(prefix, body))
        chunks: list[CorpusChunk] = []
        for ordinal, text in enumerate(payloads, start=1):
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunks.append(
                CorpusChunk(
                    chunk_id=f"{document.source_id}-{ordinal:03d}-{digest[:12]}",
                    source_id=document.source_id,
                    ordinal=ordinal,
                    text=text,
                    source_version=document.source.version,
                    effective_date=document.source.effective_date,
                    priority=document.source.priority,
                    topics=document.source.topics,
                    audiences=document.source.audiences,
                    content_sha256=digest,
                )
            )
        return tuple(chunks)

    def _split_long(self, prefix: str, body: str) -> tuple[str, ...]:
        if len(prefix) + len(body) <= self.max_chars:
            return ((prefix + body).strip(),)
        sentences = [item.strip() for item in re.split(r"(?<=[.!?…])\s+", body) if item.strip()]
        parts: list[str] = []
        current = ""
        for sentence in sentences or [body]:
            if len(prefix) + len(sentence) > self.max_chars:
                if current:
                    parts.append((prefix + current).strip())
                    current = ""
                room = max(1, self.max_chars - len(prefix))
                for offset in range(0, len(sentence), room):
                    parts.append((prefix + sentence[offset : offset + room]).strip())
                continue
            candidate = sentence if not current else f"{current} {sentence}"
            if len(prefix) + len(candidate) > self.max_chars:
                parts.append((prefix + current).strip())
                current = sentence
            else:
                current = candidate
        if current:
            parts.append((prefix + current).strip())
        return tuple(parts)


def ingest_corpus(root: Path | str, *, max_chunk_chars: int = 1200) -> CorpusIngestionResult:
    """Validate and chunk a package, preserving every failure in a typed result."""

    report = validate_corpus_package(root)
    if not report.valid or report.manifest is None:
        return CorpusIngestionResult(
            manifest=report.manifest,
            sources=report.manifest.sources if report.manifest else (),
            chunks=(),
            accepted_source_ids=(),
            skipped_source_ids=tuple(document.source_id for document in report.documents),
            errors=report.errors,
            chunking_policy=CHUNKING_POLICY_VERSION,
            content_sha256="",
        )
    chunker = CorpusChunker(max_chars=max_chunk_chars)
    chunks = tuple(chunk for document in report.documents for chunk in chunker.chunk(document))
    errors: list[CorpusValidationIssue] = []
    accepted: list[str] = []
    for document in report.documents:
        if any(chunk.source_id == document.source_id for chunk in chunks):
            accepted.append(document.source_id)
        else:
            errors.append(
                CorpusValidationIssue(
                    "empty_chunk_set",
                    "validated document produced no chunks",
                    f"source:{document.source_id}",
                    document.source_id,
                )
            )
    canonical = json.dumps(
        [
            {
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "ordinal": chunk.ordinal,
                "text": chunk.text,
                "content_sha256": chunk.content_sha256,
            }
            for chunk in chunks
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return CorpusIngestionResult(
        manifest=report.manifest,
        sources=report.manifest.sources,
        chunks=chunks,
        accepted_source_ids=tuple(accepted),
        skipped_source_ids=(),
        errors=tuple(errors),
        chunking_policy=CHUNKING_POLICY_VERSION,
        content_sha256=hashlib.sha256(canonical).hexdigest(),
    )
