"""Проверка полноты и уникальности реестра Markdown-документов проекта."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


PATH_CELL = re.compile(r"^\|\s*`([^`]+)`\s*\|")
ALLOWED_STATUSES = {
    "active",
    "planning_only",
    "proposed",
    "accepted",
    "in_progress",
    "complete",
    "blocked",
    "map ready for child execution",
    "superseded",
    "retired",
}


@dataclass(frozen=True)
class RegistryRow:
    path: str
    status: str
    line_number: int
    cells: tuple[str, ...]


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _normalize_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def discover_markdown(docs_root: Path) -> set[str]:
    return {
        path.relative_to(docs_root).as_posix()
        for path in docs_root.rglob("*.md")
        if path.is_file()
    }


def parse_registry(registry_path: Path) -> tuple[list[RegistryRow], list[str]]:
    rows: list[RegistryRow] = []
    malformed: list[str] = []
    for line_number, line in enumerate(registry_path.read_text(encoding="utf-8").splitlines(), start=1):
        match = PATH_CELL.match(line)
        if match is None:
            continue
        if not match.group(1).replace("\\", "/").endswith(".md"):
            continue
        cells = tuple(cell.strip() for cell in line.strip().split("|")[1:-1])
        if len(cells) < 7:
            malformed.append(f"line {line_number}: expected at least 7 table cells")
            continue
        path = _normalize_path(match.group(1))
        status = cells[3].strip("`").strip()
        rows.append(RegistryRow(path=path, status=status, line_number=line_number, cells=cells))
    return rows, malformed


def audit(docs_root: Path, registry_path: Path) -> list[str]:
    findings: list[str] = []
    if not docs_root.is_dir():
        return [f"docs root does not exist: {docs_root}"]
    if not registry_path.is_file():
        return [f"registry does not exist: {registry_path}"]

    actual = discover_markdown(docs_root)
    rows, malformed = parse_registry(registry_path)
    findings.extend(malformed)
    registered = [row.path for row in rows]
    registered_set = set(registered)
    counts = Counter(registered)
    duplicate_paths = sorted(path for path, count in counts.items() if count > 1)
    missing = sorted(actual - registered_set)
    extra = sorted(registered_set - actual)
    invalid_statuses = sorted(
        f"{row.path} (line {row.line_number}): {row.status!r}"
        for row in rows
        if row.status not in ALLOWED_STATUSES
    )
    blank_fields = sorted(
        f"{row.path} (line {row.line_number})"
        for row in rows
        if any(not cell.strip().strip("`") for cell in row.cells[1:])
    )

    if missing:
        findings.append("missing: " + ", ".join(missing))
    if extra:
        findings.append("extra: " + ", ".join(extra))
    if duplicate_paths:
        findings.append("duplicate_paths: " + ", ".join(duplicate_paths))
    if invalid_statuses:
        findings.append("invalid_statuses: " + "; ".join(invalid_statuses))
    if blank_fields:
        findings.append("blank_fields: " + ", ".join(blank_fields))

    print(
        "document registry audit: "
        f"actual={len(actual)} registry_rows={len(registered)} "
        f"registry_unique={len(registered_set)} missing={len(missing)} "
        f"extra={len(extra)} duplicate_paths={len(duplicate_paths)}"
    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = _default_root()
    parser.add_argument("--docs-root", type=Path, default=root / "docs")
    parser.add_argument("--registry", type=Path, default=root / "docs" / "document-registry.md")
    args = parser.parse_args()
    findings = audit(args.docs_root.resolve(), args.registry.resolve())
    if findings:
        print("document registry audit: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("document registry audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
