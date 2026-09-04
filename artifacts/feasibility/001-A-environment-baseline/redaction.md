# Redaction record

- Evidence contains no password, token, private key, model secret or audio.
- The local WSL credential file was not read into the evidence; existing bootstrap evidence remains the only reference
  to the successful passworded sudo check.
- Raw outputs contain only environment identity, package metadata, GPU metadata, paths and worktree classification.
