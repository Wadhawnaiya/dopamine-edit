# Validation

Validated on Linux with Python 3.14, FFmpeg 9.0.2 and HyperFrames CLI 0.9.15.
The CI suite additionally targets Python 3.12 / Node.js 22 on Ubuntu.

## Offline regressions

```bash
PYTHONDONTWRITEBYTECODE=1 python3 skills/dopamine-edit/scripts/test_pipeline.py
```

The suite uses generated source video/audio and controlled CLI stand-ins. It
checks real FFmpeg encoding/decoding and music preparation without requiring
network access, account credentials, GPU, Whisper model downloads or a Chrome
render for every unit test.

Covered music cases include metadata ranking, declared-vocal exclusion,
insufficient track duration, license declaration failure, downloading/preparing
a local excerpt, absent music, unmounted music, zero track gain, changed bed
hash and packaged attribution. Existing rendering/source-review protections
remain in the same suite.

## Live smoke checks

- Public catalog search returned relevant instrumental metadata.
- A selected Incompetech track was downloaded from its original audio URL.
- The current CC BY declaration, selected catalog record and attribution were
  retained outside the repository.
- A 12-second bed was trimmed/faded, probed and decoded.
- A small real HyperFrames project rendered with that downloaded bed mounted as
  `bgm-bed`; the full finish path passed, including timeline/music identity,
  encode/decode, 12-second duration and final audio measurements.
- Measured encoded mix: **−15.42 LUFS integrated**, **−3.49 dBTP**, within the
  configured −14 LUFS ±2 / ≤−1 dBTP gate.

The smoke fixture is technical test media, not an artistic sample or a delivery
made from anyone's footage. The music was measured, **not listened to**. No
claim is made that matching catalog text guarantees musical taste, that every
website will remain accessible, or that a license eliminates all Content ID
disputes. Test media/downloads and local machine paths are excluded from git.

The install helper was also exercised twice in an isolated destination to check
first install and backup-before-update behavior. No real watcher service was
enabled by tests.
