# 007-A: команды и результаты

Дата исполнения: `2026-09-13`  
Target runtime: CPython `3.14.7t`, Ubuntu 24.04/WSL2, user `sipbot`  
Основной executable: `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`  
Combined live executable: `/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python`

## Источник, patch и установка

| Объект | Значение |
|---|---|
| Distribution | `webrtcvad-wheels==2.0.14` |
| Distribution license | MIT |
| Source archive SHA256 | `5f59c8e291c6ef102d9f39532982fbf26a52ce2de6328382e2654b0960fea397` |
| Patch | [`patches/webrtcvad-wheels-2.0.14-free-threading.patch`](../../../../patches/webrtcvad-wheels-2.0.14-free-threading.patch) |
| Patch SHA256 | `bbfb5d441939e078ca3f3445ea539b6cd671ee998a585130db8c0144950d6d50` |
| Patched wheel SHA256 | `40d7448a7f1ffca3e143918da94483b76adb5b0cbc1bc6a26be7c3aaa578539d` |
| Installed native extension SHA256 | `39849a1fbe4435263c7ad67d5890818a7200803dd5427c61e1bd7f87ac885236` |

Source archive и patched wheel сохранены рядом с этим файлом для воспроизводимой пересборки. Патч применяется к
`cbits/pywebrtcvad.c` из source archive.

## Authoritative probe

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc "cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I tools/webrtc_vad_nogil_probe.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/007-webrtc-vad/007-A"
```

Результат: exit code `0`, `status=pass`, JSON — [`webrtc-vad-runtime.json`](webrtc-vad-runtime.json).

Повторено тем же probe в combined live runtime:

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc "/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I /mnt/c/devel/sip-bot/tools/webrtc_vad_nogil_probe.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/007-webrtc-vad/007-A/c4-runtime"
```

Результат: exit code `0`, `status=pass`, JSON — [`c4-runtime/webrtc-vad-runtime.json`](c4-runtime/webrtc-vad-runtime.json).

Оба manifest фиксируют:

- `Py_GIL_DISABLED=1`, `gil_before_import=false`, `gil_after_import=false`, `gil_after_construct=false`,
  `gil_after_operation=false`, `gil_after_concurrency=false`;
- 4 sample rates × 3 допустимых frame durations (`8/16/32/48 kHz`, `10/20/30 ms`);
- 8 independent VAD instances в controlled concurrency без ошибок;
- явный отказ invalid `8000/9 ms`, `8000/40 ms`, `11025/20 ms`;
- `gpu_required=false`, `live_sip_evidence=false`.

## Дополнительные проверки

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -m compileall -q tools/webrtc_vad_nogil_probe.py src/sip_bot/speech/vad.py'
```

Результат: exit code `0`.

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c "import sys; sys.path.insert(0, \"/mnt/c/devel/sip-bot\"); sys.path.insert(0, \"/mnt/c/devel/sip-bot/src\"); from sip_bot.speech.vad import WebRtcVadCandidate; print(type(WebRtcVadCandidate(mode=2)).__name__)"'
```

Результат: exit code `0`, напечатано `WebRtcVadCandidate`.
