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

Covered music cases include metadata ranking, declared-vocal exclusion
(singular/plural and negated descriptions), insufficient track duration,
license declaration failure, downloading/preparing a local excerpt, absent
music, unmounted music, zero/muted automation gain, changed playback rate or
source offset, unreadable automation, missing timeline coverage, silently
replaced beds, changed license evidence, catalog record, attribution or identity,
explicit-policy omission and legacy-project handling. Existing
rendering/source-review protections remain in the same suite.

Brand-layer cases include the deterministic luminance×saturation cutout (alpha
present, coverage recorded, idempotent rebuild), install into a project, refusal
when the project image differs, changed asset hash, wrong clip id or `src`,
incomplete timeline coverage, unreadable automation, and explicit `expect_brand`
policy. Tests for the gate build a synthetic brand stand-in; the owner's real
photo is never committed.

Preview-checkpoint cases include delivery blocked without an approval, approval
allowing delivery, approval invalidated by a composition edit, `preview.sh`
writing only under `preview/` (never `final/`), refusing a missing draft or a
delivery render passed as a preview, and the unattended `DOPAMINE_SKIP_PREVIEW=1`
bypass.

Voice-priority (mix) cases include the default 16 dB bed-to-voice separation
gate, a loud bed being refused at default and allowed when the plan explicitly
relaxes the requirement, the encoded mix's `voice_contrast_db` measurement, and
a strict `min_voice_contrast_db` failing a flat mix. Beds are prepared at -32
LUFS with `music_separation_db` / `min_voice_contrast_db` validated in the
delivery plan.

## Live smoke checks

- Public catalog search returned relevant instrumental metadata.
- A selected Incompetech track was downloaded from its original audio URL.
- The current CC BY declaration, selected catalog record and attribution were
  retained outside the repository.
- A 12-second bed was trimmed/faded, probed and decoded.
- The brand cutout was built from the owner's photo (recipe v1, alpha coverage
  16.7%), installed into the project and mounted as `brand-layer`.
- A small real HyperFrames project rendered with that downloaded bed mounted as
  `bgm-bed` **and** the brand layer mounted; the finish path verified source
  identity, license evidence, attribution, brand hash and timeline coverage
  before encoding.
- Mix policy, on a fixture with a synthetic dialogue track and a real downloaded
  master: a bed at gain 2.0 was **refused** (13.6 dB separation, needs 16); the
  same bed at gain 1.0 was accepted through preview → approval → delivery with
  **−33.7 LUFS** bed level, **19.7 dB** separation, **20.1 dB** voice contrast,
  and a master at **−14.09 LUFS / −4.35 dBTP**. The same bed at the loud gain
  flattened contrast to 5.7 dB — the failure mode the metric catches.
- Measured encoded mix: **−15.66 LUFS integrated**, **−3.70 dBTP**, within the
  configured −14 LUFS ±2 / ≤−1 dBTP gate. A decoded frame confirmed the sign is
  visible over the footage at the intended low opacity.

The smoke fixture is technical test media, not an artistic sample or a delivery
made from anyone's footage. The music was measured, **not listened to**. No
claim is made that matching catalog text guarantees musical taste, that every
website will remain accessible, or that a license eliminates all Content ID
disputes. Audibility is checked from bed level and timeline gain/automation;
there is no isolated stem render. Test media/downloads and local machine paths
are excluded from git.

The install helper was also exercised twice in an isolated destination to check
first install and backup-before-update behavior. No real watcher service was
enabled by tests.

The multi-install sync helper was checked for: read-only `--check` drift
detection, `--dry-run`, backup-before-write, post-write hash verification,
`--prune` preserving local brand assets, running from the repo and from an
installed copy, and skipping the source when it is also listed as a target.
