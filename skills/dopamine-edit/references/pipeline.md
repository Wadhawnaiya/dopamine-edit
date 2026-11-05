# Pipeline commands and acceptance gates

Use the loaded directory as `SKILL_DIR`. Set `SOURCE`, collision-safe `SLUG`,
`PROJECT_ROOT` and a new `OUT` from the scan. Examples assume Bash on this host;
never run literal placeholders. Installed CLI `--help` and loaded contracts win
over stale examples. Record intentional deviations.

## 1. Preflight

```bash
bash "$SKILL_DIR/scripts/bootstrap.sh"
python3 "$SKILL_DIR/scripts/scan_raw.py" --root "$PROJECT_ROOT" --json --all
```

Bootstrap records tools and optional Agent-Reach/yt-dlp availability. It uses
`npx hyperframes`, **not** bare `hyperframes` (which may launch the desktop here).
Set `DOPAMINE_HF_VERSION` to an exact tested version to pin all helpers in a run.
`npx` may need the CLI package fetched on a new machine; unavailable offline is
a blocker, not permission to install globally.

Maintenance, only when authorized:

```bash
bash "$SKILL_DIR/scripts/bootstrap.sh" --update --refresh-refs
```

`--update` resolves/checks the latest cached CLI for this invocation, not a global
upgrade or a skills update. Use the reported exact version as
`DOPAMINE_HF_VERSION` in subsequent commands; it does not rewrite project pins.

Template refresh is fast-forward-only and refuses dirty/diverged repositories.
Never hard-reset. Setup JSON records versions, tools, doctor, template commit/
count. Doctor exits zero even on findings: inspect `.ok` and relevant checks.
Optional Docker/provider failures need not block local rendering; Node 22+,
FFmpeg/FFprobe and usable Chrome do.

## 2. Copy/proxy and analyze

Probe actual raw media read-only:

```bash
ffprobe -v error -show_streams -show_format -of json "$SOURCE"
```

Copy compatible files with their original extension; renaming MOV to MP4 is not
a transcode. Example for normal SDR sources needing normalization:

First capture immutable source identity (also required by the finish helper):

```bash
python3 "$SKILL_DIR/scripts/scan_raw.py" --root "$PROJECT_ROOT" \
  --record-source "$SOURCE" --output "$OUT"
```

Re-run this check after copying. It refuses a changed source instead of replacing
`SOURCE.json`; use a new output revision if raw changes.

```bash
ffmpeg -n -i "$SOURCE" -map 0:v:0 -map '0:a:0?' \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart "$OUT/assets/source.mp4"
```

Handle rotation, HDR tone mapping and VFR→chosen CFR with `/media-use`; this
example alone does not solve them. Verify color/duration/sync. Use one source/
proxy clock for voice, matte and captions.

```bash
python3 "$SKILL_DIR/scripts/analyze_clip.py" "$WORK_SOURCE" \
  --out "$OUT/assets/analysis" --json
bash "$SKILL_DIR/scripts/transcribe.sh" "$WORK_SOURCE" --language hi \
  --model medium --json --to srt --output "$OUT/assets/audio/transcript.srt"
```

Omit language for unknown/mixed speech; default `small` is multilingual. Known
English can use `--language en --model small.en`. Confirm actual word-JSON path
in CLI output; `--output` may control only SRT/VTT. Preserve original transcript,
correct ASR against audio, derive output-time captions. Do not use `--optional`
to waive meaningful speech. Inspect images and later windows if analysis capped.
Only explicit English may use this wrapper's auto/Parakeet fallback. Mixed or
unknown language stays multilingual Whisper on failure; no silent engine switch.

## 3. References and style

Read [reference-research.md](reference-research.md) for Agent-Reach/yt-dlp routes,
budgets, provenance and rights. References need not block a buildable edit.

```bash
python3 "$SKILL_DIR/scripts/match_style.py" \
  --query "<subject mood visual nouns>" --category motion \
  --tags canvas,svg,gsap,threejs,shader,particles --limit 8 --json \
  --download-posters "$OUT/assets/moodboard"
python3 "$SKILL_DIR/scripts/match_style.py" --prompt "$PARENT_SLUG"
```

No cached library → built-in taxonomy in `style-dna.md`, not invented parent URLs.
Write `REFERENCES.md` and `STYLE.md`.

After source/transcript analysis, read `background-music.md` and write `MUSIC.md`.
Search licensed instrumental candidates for the actual emotion/energy/speech and
duration. After scaffolding, download/prepare the selected track into the project;
set `expect_music: true`, mount `bgm-bed`, then duck/carve under speech. No random
music before analysis, no unlicensed reference-song ripping, no silent omission.

Install the brand layer into every project after scaffolding
(`brand.py install --project ...`), mount `brand-layer` for the full duration and
set `expect_brand: true`; see `brand-layer.md`. This is the owner's own neon
sign, not optional decoration.

## 4. Plan, matte, scaffold

`BRIEF.md`: `workflow: general-video`, `flow: automation`, `storyboard: no`,
message, audience, destination, duration. `STORYBOARD.md` still has timed
`## Frame N` blocks: scene path, source window, blueprint/rules, caption, audio
cue, purpose. No approval stop for an explicitly automated video job.

`EDIT.md` is timing authority: source in/out, output start/end, speed, audio,
matched matte/plate ranges, output captions. Inserts over continuing dialogue
replace visuals, not the dialogue clock. Freezes must not repeat/omit speech.

```bash
bash "$SKILL_DIR/scripts/matte.sh" "$WORK_SOURCE" "$OUT/assets/matte"
npx hyperframes init "$OUT/project" --non-interactive --example=blank \
  --skill=dopamine-edit --resolution portrait --skip-skills
```

Matte retained footage where practical; record its source offset. Check decoded
alpha at multiple motion/occlusion times, not only its tag. Plate is an alpha
hole, not a clean background. Bad matte → mask/full-frame fallback.

Use the pinned CLI consistently if selected. Scaffold into a new path and read
its `AGENTS.md`. Copy assets or verify symlinks (sibling assets from `project/`
are `../assets`, **not** `../../assets`). No unresolved remote assets/fonts/CDNs.

## 5. Build contracts

Load current `/hyperframes-core` format reference; this is only a checklist:

- Root canvas/duration/FPS match the plan; proper clip IDs, timing and tracks.
- Source in points, speed, voice/matte/plate follow the same edit map.
- Registered paused seek-safe timeline per scene; framework-owned media playback.
- Animate wrappers; no timed-clip visibility or CSS/GSAP transform conflicts.
- No clocks/unseeded randomness/render-time network; local glyph-complete fonts.
- Separate footage/graphics/captions/voice/bed/SFX tracks; no duplicate dialogue.
- No unlicensed footage, logos or music promoted from research.

Search named registry looks before hand-building. Use supported `.motion.json`
assertions for hook visibility, caption containment and motion. No global check
bypasses. Build/seek a representative scene, inspect edges and phone readability.
Talking-head clock is speech, not beats; music-led edits use `/music-to-video`.

## 6. Audio and captions

Use `/embedded-captions` for identity, not permission to alter all footage.
Captions follow **output** voice timing. Check cuts, names, negations and final
words. A paraphrased hook must not masquerade as a verbatim quote.

Use authorized media and `/hyperframes-audio` mixing. BGM/hits support speech;
not every cut needs a hit. Measure master: target -14 LUFS integrated (±2 LU),
true peak ≤ -1 dBTP (0.2 dB measurement tolerance). Intentional pauses are fine.

## 7. Finish and review

Read [quality-gates.md](quality-gates.md); write exact `DELIVERY.json`, then:

```bash
bash "$SKILL_DIR/scripts/finish.sh" "$OUT/project" "$SLUG" --json
```

Every attempt uses `final/attempt-*/`; drafts stay there. Delivery bypass flags
are refused. JSON `ok`/`browserSkipped`, proof capture and render verification
are required. Failures do not expose stale outputs as new successes. Existing
MP4s are never overwritten. Success means **candidate awaiting review**.
If stable output paths already exist, the helper returns the fresh attempt's
candidate successfully; review/mark that exact path rather than overwriting.

Inspect decoded scene midpoints/cut seams and audio, not only source/Studio or
contact sheets. Record actual evidence and any review limitations. Fix concrete
defects within the bounded retries in `SKILL.md`. Only matching QA/review/source
fingerprint allows `scan_raw.py --mark`. No direct state edits to bypass it.

## 8. Failure routing

| Failure | Response |
| --- | --- |
| Empty raw vs all processed | Say which; show recent deliveries |
| In-progress copy/corrupt source | Leave pending; report source |
| Platform/login/captcha/rate limit | Stop route; local/cached inspiration |
| ASR unavailable for audible speech | Retry correct model/window; no fake captions |
| Bad matte | Mask/full-frame fallback; document |
| Missing BGM/license | Source voice + authorized SFX; disclose |
| Lint error / skipped browser | Fix before trusting layout/contrast |
| Black panel/bad seek | Check paths, mounts, timing and timeline registration |
| Silent/duplicated audio | Check IDs/mutes/source ranges/mixer |
| Decode/format/loudness/sync failure | Correct project and rerender; leave pending |
| Version mismatch | Read help; pin working CLI; no global mid-edit update |
| Repeated unresolved defect | Preserve project/logs; report blocked, not delivered |
