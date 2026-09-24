# Map-008-A execution closeout

Статус: `complete`  
Дата: `2026-09-13`  
Evidence: `runs/mode-sweep/summary.json`

## Результат

Standalone calibration выполнена на target free-threaded CPython `3.14.7t`.
Корпус содержит пять русских фраз одного XTTS-v2 reference voice, взятых из
принятого Map-007 J4 fixture, и заново собранных с контролируемыми паузами
`240/480/620/700 ms`. Генератор не вызывает модель повторно; provenance,
source hash, phrase hashes и timing manifest сохранены.

Corpus:

- `corpus/calibration-corpus.wav` — mono PCM S16LE, 8 kHz, 14.58 s;
- SHA-256: `a031570e9954d249851997f33252ccc783dc27f0511cee3bb427a1d32579f5c8`;
- `corpus/manifest.json` — revision 1, immutable-after-build;
- `corpus/phrases/phrase-01.wav` … `phrase-05.wav` — исходные речевые сегменты.

## Mode sweep

Команда:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I tools/vad_calibration_probe.py --corpus-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-A/corpus --output-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-A/runs/mode-sweep --repeat 2'
```

Exit code: `0`. Все четыре режима обработали одни и те же `729` кадров, с
явным PCMU encode/decode round-trip и повторным replay. Все повторы
детерминированы.

| Mode | Missed speech | False speech | Mean abs onset | Mean abs offset | Score |
|---:|---:|---:|---:|---:|---:|
| 0 | 0.7246% | 8.4746% | 48.4 ms | 102.4 ms | 0.13605765 |
| 1 | 0.7246% | 7.9096% | 48.4 ms | 102.4 ms | 0.13040793 |
| 2 | 1.2681% | 2.2599% | 7.6 ms | 72.8 ms | **0.09404467** |
| 3 | 2.5362% | 1.6949% | 11.6 ms | 84.8 ms | 0.15340075 |

Рекомендация: `VAD_MODE=2`. Это решение основано на полном corpus и явной
формуле score, а не на одном WAV или субъективном прослушивании. ASR в A не
использовался.

## Corrective pass и ограничения

Первый target запуск probe выявил отсутствующий в bootstrap путь к корневому
пакету `config`; исправлен только test-tool import bootstrap и выполнен
повторный запуск. В unit test был исправлен собственный ошибочный размер
синтетического fixture. Production speech boundary не изменялась.

Следующий child получил corpus revision/hash, raw masks `mode-0.json` …
`mode-3.json`, scorecard, runtime/GIL evidence и exact command.

Ограничение: это controlled single-voice TTS baseline; robustness на
человеческих голосах и шуме остаётся deferred scope.
