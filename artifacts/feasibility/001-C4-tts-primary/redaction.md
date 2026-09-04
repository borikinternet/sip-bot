# 001-C4 TTS primary — redaction and artifact policy

- Model weights и voice assets не копируются в repository/evidence root автоматически.
- `tts-sample.wav` разрешён только как короткий synthetic TTS result будущего успешного
  operation; он не является записью пользовательского разговора.
- Отдельный raw `.pcm` dump не создаётся.
- В evidence допускаются commands, versions, stdout/stderr, exit codes и hashes результата.
- Локальные пути и user-specific secrets не должны попадать в manifest без необходимости;
  текущий preflight содержит только runtime path, не credentials.
- При отсутствии лицензии, provenance или права на demo-use operation останавливается с
  blocker; asset не публикуется молча.

