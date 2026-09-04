# C2 offline Russian fixture metadata

Статус: source selected, local audio not materialized in restricted pre-GPU stage.

## Источник

- Dataset: Mozilla Common Voice Scripted Speech 25.0 — Russian.
- Dataset page: <https://commonvoice.mozilla.org/en/datasets>.
- Locale: `ru`.
- Task: ASR.
- Format at source: MP3; operation probe will decode locally and make conversion explicit.
- License: CC0-1.0, согласно странице Mozilla Data Collective.
- Provenance: one short validated clip selected from the Russian `validated.tsv` metadata of that release.

## Selection rule for the GPU stage

Select exactly one validated Russian clip satisfying:

1. 3–10 seconds duration;
2. one speaker and no personally identifying content in the sentence text;
3. available transcript in the release metadata;
4. no live SIP/PBX origin and no recording made for this project.

Before operation, the executor must save only the fixture metadata and, if local retention is needed for the probe,
the short offline fixture itself under the C2 evidence root. The record must include source release, relative clip ID,
transcript from metadata, byte size, SHA-256, source format, decoded rate/channels and conversion path. The clip must
not be committed to the repository unless the project owner separately approves that redistribution.

The selected source is suitable for a Russian ASR smoke, but it does not by itself establish phone-channel robustness,
WER, MOS or production quality.

## Execution materialization (2026-08-27)

The originally selected Common Voice 25.0 distribution was not anonymously downloadable from Mozilla Data Collective:
its current download path requires authenticated access. To avoid fabricating a 25.0 fixture, the preparation stage
used a public parquet mirror whose card and embedded row metadata identify the actual upstream release as Common Voice
Scripted Speech 26.0. This is a provenance gap to review if strict 25.0 identity is required; it is not an ASR fallback.

Mirror provenance:

- Canonical repository: `Peacockery/common-voice-scripted-speech-26`.
- Repository revision observed through the Hugging Face resolve response:
  `b4d8b94d43831475de59a455345acf6945cfd66e`.
- Alias used for download: `https://huggingface.co/datasets/Peacockery/common-voice-scripted-speech-25-0`.
- Canonical shard:
  `data/dev/common_voice_scripted_speech_26_0__ru__cmqinj9g500vsnr07qf4hmr3j.parquet`.
- Shard size: `379469589` bytes.
- Shard LFS/content SHA-256 and mirror file OID:
  `3fac25fb314f316db981a11ef5ba5027b6632a87910dfd32007510bdeb43d394`,
  `33f6015f6db29dfcbe9ea8e1625892723e7a5d04`.
- Dataset card: CC0-1.0; license URL: `https://spdx.org/licenses/CC0-1.0.html`.

Selected row:

- `source_audio_path`: `cv-corpus-26.0-2026-06-12/ru/clips/common_voice_ru_18856149.mp3`.
- `source_dataset_id`: `cmqinj9g500vsnr07qf4hmr3j`.
- `source_archive`: `common-voice-scripted-speech-26-0-russia-49c8467c.tar.gz`.
- `upstream_split`: `dev`; locale: `ru`.
- `sentence_id`: `1034f372d922ab4d04f6c981ca511d76f0217e60ddb3ac123b10ec48b2ade354`.
- Transcript: `Мы считаем, что это следующий логический шаг.`
- Source duration metadata: `4368 ms`.

Local fixture:

- Evidence path: `artifacts/feasibility/001-C2/fixture.mp3`.
- External extraction path: `/home/sipbot/.local/fixtures/common-voice-26-ru/fixture.mp3`.
- Size: `34989` bytes.
- SHA-256: `c176ba70ae532a64800290329d9f77d7d750f3a580e08986bfb2266cbd528794`.
- Container/codec: MPEG Layer III, 64 kbps, 48 kHz, mono (`mp3float` in PyAV).
- Decoded verification: 48 kHz, mono, `4368 ms`; no live SIP/PBX recording.

The current probe makes the model-side conversion explicit as PyAV decode/resample to float32 16 kHz mono. The
production media boundary remains PCMU/G.711 μ-law 8 kHz mono → PCM S16LE 8 kHz mono; a full PCMU/RTP path is outside
this fixture-materialization step. Do not commit the copied audio file without a separate owner decision about
redistribution of the CC0 source asset.
