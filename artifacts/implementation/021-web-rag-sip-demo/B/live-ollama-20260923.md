# 021-B live Ollama evidence — 2026-09-23

Статус: `pass` для локального session-scoped RAG preparation path.

## Environment

- WSL distribution: `Ubuntu-24.04`.
- Existing binary: `/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama`.
- Ollama version: `0.33.1`.
- Models discovered in `/home/sipbot/.ollama/models`:
  - `embeddinggemma:latest`, embedding length `768`;
  - `c3-qwen35-9b-q4km:latest`, Qwen35 `9.0B`, `Q4_K_M`.
- Runtime log detected `NVIDIA GeForce RTX 5060 Ti`, CUDA compute `12.0`, VRAM `15.9 GiB`.
- `ollama serve` was started in the existing Ubuntu WSL environment and listens on `127.0.0.1:11434`.
  Windows-side `http://127.0.0.1:11434/api/version` returned HTTP `200`, so the Windows demo sidecar can use its
  configured default endpoint.

## Live checks

The following checks passed:

1. `GET /api/version` returned `{"version":"0.33.1"}`.
2. `GET /api/tags` returned both required models.
3. `/api/embed` with `embeddinggemma:latest` returned a vector; the model metadata reports dimension `768`.
4. `OllamaMetadataProvider` through the repository's typed `LlmFacade` returned title, topic, description and three
   Russian questions for a SIP/WebRTC probe document.
5. `RagPreparationCoordinator` through the same live chat and embedding facade built, self-loaded and published a
   temporary immutable artifact:

   ```text
   title: SIP и WebRTC в FreeSWITCH
   topic: Интеграция браузерных SIP-звонков и ботов
   index_version: conference-live-probe-session-e2e5b8e76937
   dimension: 768
   item_count: 1
   artifact_exists: True
   ```

The temporary probe artifact was created below a temporary directory and removed after the check. No baseline index
was changed.

## Limitation

Ollama binds to WSL loopback. The Windows host reaches it through WSL localhost forwarding, while the WSL IP address
`172.22.89.126:11434` intentionally refuses connections. This is compatible with the current Windows-side demo
backend and is not a public deployment claim.
