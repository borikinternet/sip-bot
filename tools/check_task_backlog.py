"""Проверка структуры и уникальности task backlog проекта."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


ID_CELL = re.compile(r"^\|\s*`(TASK-[A-Z0-9-]+)`\s*\|")
ALLOWED_STATUSES = {
    "open",
    "in_progress",
    "blocked",
    "deferred",
    "done",
    "out_of_scope",
    "superseded",
}
ALLOWED_PRIORITIES = {"high", "medium", "low"}


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_rows(backlog_path: Path) -> tuple[list[tuple[str, int, tuple[str, ...]]], list[str]]:
    rows: list[tuple[str, int, tuple[str, ...]]] = []
    malformed: list[str] = []
    for line_number, line in enumerate(backlog_path.read_text(encoding="utf-8").splitlines(), start=1):
        match = ID_CELL.match(line)
        if match is None:
            continue
        cells = tuple(cell.strip() for cell in line.strip().split("|")[1:-1])
        if len(cells) != 8:
            malformed.append(f"line {line_number}: expected 8 table cells, got {len(cells)}")
            continue
        rows.append((match.group(1), line_number, cells))
    return rows, malformed


def audit(backlog_path: Path) -> list[str]:
    if not backlog_path.is_file():
        return [f"backlog does not exist: {backlog_path}"]

    rows, findings = parse_rows(backlog_path)
    if not rows:
        findings.append("no task rows found")

    ids = [task_id for task_id, _, _ in rows]
    duplicate_ids = sorted(task_id for task_id, count in Counter(ids).items() if count > 1)
    if duplicate_ids:
        findings.append("duplicate_ids: " + ", ".join(duplicate_ids))

    invalid_statuses: list[str] = []
    invalid_priorities: list[str] = []
    blank_fields: list[str] = []
    for task_id, line_number, cells in rows:
        status = cells[2].strip("`")
        priority = cells[3].strip("`")
        if status not in ALLOWED_STATUSES:
            invalid_statuses.append(f"{task_id} (line {line_number}): {status!r}")
        if priority not in ALLOWED_PRIORITIES:
            invalid_priorities.append(f"{task_id} (line {line_number}): {priority!r}")
        if any(not cell.strip().strip("`") for cell in cells[1:]):
            blank_fields.append(f"{task_id} (line {line_number})")

    if invalid_statuses:
        findings.append("invalid_statuses: " + "; ".join(invalid_statuses))
    if invalid_priorities:
        findings.append("invalid_priorities: " + "; ".join(invalid_priorities))
    if blank_fields:
        findings.append("blank_fields: " + ", ".join(blank_fields))

    print(f"task backlog audit: rows={len(rows)} unique_ids={len(set(ids))}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = _default_root()
    parser.add_argument("--backlog", type=Path, default=root / "docs" / "task-backlog.md")
    args = parser.parse_args()
    findings = audit(args.backlog.resolve())
    if findings:
        print("task backlog audit: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("task backlog audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
