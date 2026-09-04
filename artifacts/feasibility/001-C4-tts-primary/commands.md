# 001-C4 TTS primary — commands and execution boundary

## Выполненные команды и результат

Execution выполнен в сохранённом disposable environment. Команды установки и восстановления
повторялись после временных SSL/частичных файлов; persistent package/cache lock blocker не
обнаружен. GPU/model commands ниже запускались только главным агентом.

```powershell
wsl.exe --list --quiet
wsl.exe -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t --version
wsl.exe -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -c "import sys,sysconfig; print('executable='+sys.executable); print('version='+sys.version.replace(chr(10),' ')); print('platform='+sys.platform); print('soabi='+str(sysconfig.get_config_var('SOABI'))); print('Py_GIL_DISABLED='+str(sysconfig.get_config_var('Py_GIL_DISABLED'))); print('gil_enabled='+str(sys._is_gil_enabled()))"
wsl.exe -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pip list --format=freeze
wsl.exe -d Ubuntu-24.04 -- bash -lc "find /home/sipbot -maxdepth 6 -type d \( -iname '*tts*' -o -iname '*voice*' -o -iname '*piper*' -o -iname '*coqui*' -o -iname '*silero*' -o -iname '*kokoro*' -o -iname '*vits*' \) -print 2>/dev/null | head -100"
wsl.exe -d Ubuntu-24.04 -- bash -lc "find /home/sipbot -maxdepth 7 -type f \( -iname '*.onnx' -o -iname '*.safetensors' -o -iname '*.pt' -o -iname '*.pth' -o -iname '*.bin' \) -print 2>/dev/null | head -100"
```

Результат этих проверок: target runtime и no-GIL baseline подтверждены. Фактически установлен
и проверен package set зафиксирован в `environment.json`; `pip check` чистый. Затем выполнены
свежие import-only проверки для TTS пути, результат зафиксирован в `import.json`.

Установка/восстановление exact package set выполнялась командами:

    /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -m pip install --cache-dir /home/sipbot/.cache/sip-bot-c4-xtts-v2-pip coqui-tts==0.27.5 torch==2.10.0 torchaudio==2.10.0 torchcodec==0.16.0
    /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -m pip install --force-reinstall --no-deps --cache-dir /home/sipbot/.cache/sip-bot-c4-xtts-v2-pip torch==2.10.0
    /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -m pip install --no-deps --cache-dir /home/sipbot/.cache/sip-bot-c4-xtts-v2-pip librosa==0.11.0 audioread==3.0.1 standard-aifc==3.13.0 standard-sunau==3.13.0 standard-chunk==3.13.0 audioop-lts==0.2.2
    /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -m pip install --no-deps --cache-dir /home/sipbot/.cache/sip-bot-c4-xtts-v2-pip transformers==4.57.5 tokenizers==0.22.2 huggingface-hub==0.36.2
    /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -m pip check

Exact model revision и все assets были получены через `snapshot_download` с local directory
`/home/sipbot/.cache/sip-bot-c4-xtts-v2-model` и HF cache
`/home/sipbot/.cache/sip-bot-c4-xtts-v2-hf`; resume завершился успешно, а hashes всех model files
совпали с `asset-manifest.json`.

No-GIL patches, применённые к disposable runtime:

    torchaudio-free-threading.patch
    tokenizers-free-threading.patch
    monotonic-alignment-search-free-threading.patch

В tested runtime optional package directory `triton` отключён: XTTS operation его не требует,
а импорт `triton._C.libtriton` re-enable-ил GIL. `torchcodec` не импортируется; reference audio
загружается soundfile-loader-ом, а resampling выполняет patched torchaudio.

## Команды для следующего разрешённого execution

Эти команды предназначены главному агенту и используют те же сохранённые пути; второй TTS-кандидат
не добавляется. Фактические stdout/stderr сохранены рядом с JSON evidence.

Возобновление неполной загрузки exact revision:

    /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='coqui/XTTS-v2', revision='6b8036b35d787cf43d18d640587956b9db8fd1b8', local_dir='/home/sipbot/.cache/sip-bot-c4-xtts-v2-model', cache_dir='/home/sipbot/.cache/sip-bot-c4-xtts-v2-hf', allow_patterns=['config.json','dvae.pth','mel_stats.pth','model.pth','vocab.json','LICENSE.txt','README.md','samples/en_sample.wav'], max_workers=4)"

Затем допускается выполнить только один candidate-specific operation. Он обязан:

- загрузить exact XTTS-v2 model и выполнить короткую русскоязычную synthetic TTS operation;
- сохранить результат именно этого operation как WAV/PCM в
  `artifacts/feasibility/001-C4-tts-primary/tts-sample.wav`;
- записать в `operation.json` sample rate, channels, bytes, duration и SHA-256;
- измерить время от получения конечной фразы до готового результата;
- отдельно передать первый PCM result на PCMU boundary и проверить cancellation/stale result.

Перед operation no-GIL gate был закрыт тремя exact patches и исключением необязательного Triton
из operation path. Это не разрешение использовать unpatched wheels.

```text
<TARGET_PYTHON> tools/feasibility/tts_primary_probe.py --manifest <EXECUTION_MANIFEST> --stage manifest
<TARGET_PYTHON> tools/feasibility/tts_primary_probe.py --manifest <EXECUTION_MANIFEST> --stage import
<TARGET_PYTHON> tools/feasibility/tts_primary_probe.py --manifest <EXECUTION_MANIFEST> --stage operation --allow-tts-operation
<TARGET_PYTHON> tools/feasibility/tts_primary_probe.py --manifest <EXECUTION_MANIFEST> --stage pcmu-boundary --allow-tts-operation
<TARGET_PYTHON> tools/feasibility/tts_primary_probe.py --manifest <EXECUTION_MANIFEST> --stage cancellation --allow-tts-operation
```

Probe сам выполняет только candidate-specific operation и создаёт WAV из его результата. При
отсутствии полного asset, неизвестном API, GIL failure, необходимости fallback или нового
неодобренного converter команда должна останавливать acceptance с blocker.
