# Delivery gates

Scripts prove only measured properties, not perfection. No "visual quality
passed" without inspection or claim of listening without audio-capable tools.

## 1. Before render: DELIVERY.json

Write `output/<slug>/DELIVERY.json` from the edit plan:

```json
{
  "duration": 12.4,
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "expect_audio": true,
  "expect_music": true,
  "expect_brand": true,
  "target_lufs": -14,
  "lufs_tolerance": 2,
  "max_true_peak_dbtp": -1
}
```

Positive finite duration/FPS, integer dimensions and explicit audio expectation
are required. Audio false is only for explicitly silent deliveries, documented
in the brief. Never change expectations just to fit a defective encode.
Silent delivery may omit audio or contain an all-zero AAC track; any existing
audio is still decoded and flagged for review, but silence is not a failure.

Capture `SOURCE.json` with `scan_raw.py --record-source` **before ingestion**.
The finish helper validates it before/after render and carries it into QA.
Never replace its fingerprint to bless an old project after raw media changes.

New edits must state `expect_music` explicitly (`true` by default): `MUSIC.json`
must identify a licensed, project-local bed of the correct duration, and
`finish.sh` verifies its hash, saved license/catalog/attribution evidence and
identity plus the mounted `bgm-bed` timeline clip (coverage, source offset, rate,
readable automation, effective gain). Use `expect_music: false` only with a
meaningful `music_exception` for deliberately silent/source-music/no-added-music
briefs. Only a project created before music gating may set `legacy_project: true`
to omit the field. Required music may not disappear silently on a download
failure. Credits are copied beside the candidate; carry them into the posting
description/caption as required. Audibility is checked from bed level and
timeline gain/automation, not an isolated stem — state that limit honestly.

New edits must also state `expect_brand` explicitly (`true` by default): the
owner's neon cutout must be installed (`brand.py install`) and mounted at the
root as a full-duration `brand-layer` clip with the exact
`assets/brand/logo.png` source, resolved timing and full coverage. A project
created before brand gating may set `legacy_project: true`; `false` is only for a
user-requested unbranded export. The gate also re-checks the project asset hash
against the skill asset before and after render. See
[brand-layer.md](brand-layer.md).

## 2. Composition

- `check --json --snapshots`: successful exit, `ok: true`, `browserSkipped: false`.
  Missing/malformed fields fail closed. Retain JSON; inspect warnings/sample
  counts/skipped audits. Zero-sample layout/contrast is not a clean audit.
- Fix errors; review intentional warnings. No global ignore/contrast bypasses.
- Snapshot opening, each scene midpoint, cut seams and end, plus phone-size review.
  Current `snapshot --review` captures beat/seam/phone sheets; helper's nine-frame
  baseline is not a substitute for scene-specific evidence. Times stay in range.
- Check source map, local media/fonts, seek-safety and duplicate dialogue.

## 3. Render

`finish.sh` uses a fresh `final/attempt-*` directory with no delivery bypasses or
overwrite of past MP4s. Drafts cannot be delivered. `verify_render.py` checks:

- MP4 H.264/yuv420p; planned dimensions/FPS/duration (duration tolerance
  max(0.1 s, two frames)); required AAC audio and nonempty streams.
- Full video/audio decode without reported errors, not just header probing.
- Expected audio has finite loudness/audible content; master inside target
  tolerance; true peak at most 0.2 dB over the stated ceiling.
- Audio/video stream duration mismatch >0.15 s fails when metadata is available;
  this checks gross tails, **not** lip/caption sync.
- Near-black intervals ≥0.1 s logged. Opening/near-entire black fails; other dark
  intervals require visual review rather than automatic rejection or dismissal.
- Actual decoded cover and eight proof frames exist; no silent `|| true` success.
- Exact MP4 SHA-256 binds QA to that file. Raw probe, measurements and failures
  remain available, not overwritten by a small summary.

Standalone verification:

```bash
python3 "$SKILL_DIR/scripts/verify_render.py" "$VIDEO" \
  --expect "$OUT/DELIVERY.json" --report "$QA_PATH" --proof-dir "$PROOF_DIR"
```

## 4. Evidence-backed review

Inspect decoded output vs storyboard, not just source/Studio. Review:

- opening/last frame, every scene and cut seam; no missing/black/frozen layers;
- full-size matte motion/occlusions, hair/hands, halos, color seams, frame offsets;
- glyphs/shaping/spelling/names/numbers/negations; truthful quotes;
- retimed speech/captions at each cut (aim ≤2 output frames for checked word
  onsets); no removed words/orphaned captions/truncated final phrase;
- phone readability, safe margins, face/mouth/eye clearance;
- intelligible voice, no doubled/phasey dialogue, music pumping, clipping,
  clicks or intrusive/unlicensed effects;
- payoff/story truth and evidence-backed resolution of warnings/dark intervals.

When audio playback is unavailable, review the measured mix, speech/caption
timing, waveform/silences and source ranges; set `audio_review: measured` and
explicitly disclose "audio measured, not listened to". This is a limited review,
not a listening pass; it may be delivered if no unresolved risk depends on
hearing it. Ambiguous words, suspected distortion or speech masking remain
blocked until resolved. If listening was possible use `audio_review: listened`;
an explicitly silent brief uses `audio_review: silent` with its rationale.

Write `REVIEW.json` after inspection, with actual values:

```json
{
  "status": "passed",
  "video": "final/example.mp4",
  "sha256": "<from matching QA>",
  "source_fingerprint": "<ingestion fingerprint from SOURCE.json, still matching raw>",
  "audio_review": "measured",
  "limitations": ["Audio measured, not listened to"],
  "checks": {"visual": true, "audio": true, "captions": true, "timing": true},
  "evidence": [
    "Decoded opening, scene midpoints, seams and last frame: <paths/times>",
    "Voice/caption sync and final audio: <measurements/waveform or playback tool/intervals>",
    "Warnings/fallbacks resolved: <specific findings or none>"
  ]
}
```

No copied true placeholders. Caption pass for no-speech footage means confirmed
no fake subtitles and checked designed text. Blocked/pending review stays so.
Keep `ANALYSIS.md`, `REFERENCES.md`, `STYLE.md`, `BRIEF.md`, `STORYBOARD.md`,
`EDIT.md`, `DELIVERY.json` with the project.

## 5. Mark done

`scan_raw.py --mark ... --output ...` requires delivery-quality QA success,
matching review, exact MP4 hash, current raw fingerprint and planning artifacts.
The ingestion fingerprint in `SOURCE.json`, copied into QA, must match review
and current raw too; a newly copied current fingerprint alone is insufficient.
It rejects drafts/stale reports/changed sources/incomplete review. Failed or
unreviewed clips remain pending; report project/log paths and the limitation.

## Regression checks for skill maintenance

Run `python3 scripts/test_pipeline.py` from the skill directory after changing
helpers. It uses synthetic FFmpeg media, isolated state and a controlled CLI
stand-in under `/tmp/opencode`; it does not edit user footage or install anything.
These tests exercise failure gates and packaging, not creative judgment, ASR
accuracy, every website extractor or the browser renderer. Validate the latter
with a small real HyperFrames smoke render when its contract/CLI changes.
