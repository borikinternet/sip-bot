from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from sip_bot.retrieval import (
    CORPUS_SCHEMA_VERSION,
    CorpusPackage,
    CorpusValidationError,
    validate_corpus_package,
)


PROJECT_ROOT = Path(__file__).parents[2]
SCIENCE_CORPUS = PROJECT_ROOT / "data" / "knowledge" / "corpus"
TELECOM_CORPUS = PROJECT_ROOT / "data" / "knowledge" / "telecom-corpus"
WORKSHOP_CORPUS = PROJECT_ROOT / "config" / "workshops" / "rag" / "corpus"


@pytest.mark.parametrize(
    ("root", "corpus_id", "source_count"),
    (
        (SCIENCE_CORPUS, "ru-natural-science-demo", 3),
        (TELECOM_CORPUS, "ru-telecom-voice-assistants-demo", 1),
        (WORKSHOP_CORPUS, "small-service-company-demo", 6),
    ),
)
def test_checked_in_corpus_packages_are_strict_and_typed(
    root: Path, corpus_id: str, source_count: int
) -> None:
    report = validate_corpus_package(root)

    assert report.valid is True
    assert report.errors == ()
    assert report.manifest is not None
    assert report.manifest.schema_version == CORPUS_SCHEMA_VERSION
    assert report.manifest.corpus_id == corpus_id
    assert len(report.manifest.sources) == source_count
    assert len(report.documents) == source_count
    assert tuple(source.source_id for source in report.manifest.sources) == tuple(
        sorted(source.source_id for source in report.manifest.sources)
    )
    assert all(len(document.sha256) == 64 for document in report.documents)


def test_report_is_stable_for_repeated_validation() -> None:
    first = validate_corpus_package(WORKSHOP_CORPUS).to_dict()
    second = validate_corpus_package(WORKSHOP_CORPUS).to_dict()

    assert first == second


def _copy_workshop(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    shutil.copytree(WORKSHOP_CORPUS, root)
    return root


def _manifest(root: Path) -> dict[str, object]:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, value: dict[str, object]) -> None:
    (root / "manifest.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_unknown_manifest_field_is_fail_closed(tmp_path: Path) -> None:
    root = _copy_workshop(tmp_path)
    value = _manifest(root)
    value["hidden_fallback"] = True
    _write_manifest(root, value)

    report = validate_corpus_package(root)

    assert report.valid is False
    assert any(issue.code == "unknown_field" for issue in report.errors)
    with pytest.raises(CorpusValidationError):
        CorpusPackage.load(root)


def test_duplicate_source_and_file_are_rejected(tmp_path: Path) -> None:
    root = _copy_workshop(tmp_path)
    value = _manifest(root)
    sources = value["sources"]
    assert isinstance(sources, list)
    duplicate = dict(sources[0])
    sources.append(duplicate)
    _write_manifest(root, value)

    codes = {issue.code for issue in validate_corpus_package(root).errors}

    assert {"duplicate_source_id", "duplicate_file"} <= codes


@pytest.mark.parametrize("unsafe", ("../outside.md", "/tmp/outside.md", "C:/outside.md", "nested\\file.md"))
def test_source_path_must_be_confined_posix_markdown(tmp_path: Path, unsafe: str) -> None:
    root = _copy_workshop(tmp_path)
    value = _manifest(root)
    sources = value["sources"]
    assert isinstance(sources, list)
    sources[0]["file"] = unsafe
    _write_manifest(root, value)

    report = validate_corpus_package(root)

    assert report.valid is False
    assert any(issue.code in {"unsafe_path", "invalid_path"} for issue in report.errors)


def test_invalid_utf8_document_is_reported_and_not_loaded(tmp_path: Path) -> None:
    root = _copy_workshop(tmp_path)
    value = _manifest(root)
    sources = value["sources"]
    assert isinstance(sources, list)
    target = root / sources[0]["file"]
    target.write_bytes(b"\xff\xfe\x00")

    report = validate_corpus_package(root)

    assert report.valid is False
    assert any(issue.code == "invalid_utf8" for issue in report.errors)
    assert all(document.relative_path.as_posix() != sources[0]["file"] for document in report.documents)


def test_empty_document_is_reported_instead_of_silently_skipped(tmp_path: Path) -> None:
    root = _copy_workshop(tmp_path)
    value = _manifest(root)
    sources = value["sources"]
    assert isinstance(sources, list)
    (root / sources[0]["file"]).write_text(" \n\t", encoding="utf-8")

    report = validate_corpus_package(root)

    assert report.valid is False
    assert any(issue.code == "empty_document" for issue in report.errors)


def test_duplicate_json_key_is_rejected(tmp_path: Path) -> None:
    root = _copy_workshop(tmp_path)
    raw = (root / "manifest.json").read_text(encoding="utf-8")
    raw = raw.replace('"schema_version": "rag-corpus-v1",', '"schema_version": "rag-corpus-v1",\n  "schema_version": "rag-corpus-v1",', 1)
    (root / "manifest.json").write_text(raw, encoding="utf-8")

    report = validate_corpus_package(root)

    assert report.valid is False
    assert any(issue.code == "invalid_json" for issue in report.errors)
