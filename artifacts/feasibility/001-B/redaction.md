# 001-B redaction and attribution record

- Secrets/credentials: не использовались и не записывались.
- External services: использован только официальный Python source URL для получения исходника; PBX, SIP peer,
  cloud inference и model registry не использовались.
- User worktree: staged/untracked files перечислены в `git-status.txt`; они не копировались в Linux source root.
- Paths in evidence: Linux build/runtime paths and project tool path are intentional technical provenance, not secrets.
- Output review: probe output contains no credentials; stderr был пуст на каждом запуске (tracked log contains marker
  `empty` to make that fact reviewable).
