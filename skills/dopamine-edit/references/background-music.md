# Footage-led background music

Default provider preference: **public licensed instrumental tracks**, no login,
no paid API, no automatic generation. This is a reusable preference, not
permission to download copyrighted songs from social references. HeyGen catalog
support remains optional when the user selects it and signs in.

## 1. Understand the video first

After `ANALYSIS.md`, transcript verification and the duration plan, write a short
`MUSIC.md`: story/subject, emotional arc, speech density/language, energy, target
tempo range, instrumentation, exclusions (usually vocals/strong lead melodies),
hook/payoff cue and duration. No downloading a random trending track first.

Pick an intent from the footage, e.g.:

| Footage | Music direction (not fixed templates) |
| --- | --- |
| Talking-head education / business | minimal calm groove, sparse piano/electronic, 80–110 BPM |
| Tech / product | clean bright electronic, restrained percussion, 100–125 BPM |
| Fitness / action | driving instrumental rhythm, 120–150 BPM |
| Story / suspense | sparse mysterious pulse, 70–110 BPM, no horror cliches unless warranted |
| Lifestyle / comedy | bouncy light groove, 90–125 BPM |
| Travel / emotional | warm ambient/cinematic, 60–100 BPM |

Dense speech needs less musical density, not necessarily a lower tempo. Do not
stereotype music from a speaker's language/identity. Preserve intentional silence
or already-authorized source music; do not stack two competing beds.

## 2. Search → choose → download

The built-in `scripts/music.py` searches the live **Incompetech/Kevin MacLeod**
catalog, ranks metadata, verifies its current CC BY 4.0 declaration, downloads
only the selected original, prepares an excerpt and records attribution. It uses
Python's standard library + FFmpeg/FFprobe; no ML packages, API keys or logins.
Catalog matches are suggestions, not proof of how a track sounds.

```bash
python3 "$SKILL_DIR/scripts/music.py" search \
  --query "calming bright piano minimal" --duration "$DURATION" \
  --bpm-min 80 --bpm-max 115 --limit 6 \
  --output "$OUT/assets/audio/music-shortlist.json"
```

Review 2–3 candidates' description, instruments, rhythm and usable entry point.
If playback exists, listen to short sections. Otherwise disclose metadata/
measurement-only selection; do not claim listening. Select a real returned ISRC,
write the reason in `MUSIC.md`, scaffold the project, then:

```bash
python3 "$SKILL_DIR/scripts/music.py" prepare \
  --id "$TRACK_ISRC" --query "$MUSIC_INTENT" --reason "$CHOICE_REASON" \
  --duration "$DURATION" --start "$MUSIC_SOURCE_START" \
  --project "$OUT/project" --record "$OUT/MUSIC.json"
```

Outputs are local `project/assets/audio/music/<id>/original.mp3`, `bed.wav`,
`ATTRIBUTION.txt` and `MUSIC.json`. Preparation trims an actual source interval,
adds short fades, converts to 48 kHz stereo and levels the **standalone bed**.
It never assumes the opening is the best section or silently loops a short track.
It refuses changed license declarations, bad/oversized downloads, missing audio,
silent beds and a requested interval longer than the source. A failed attempt
stays inspectable; use a fresh project/revision or another ID, never overwrite.

## 3. Mount and mix—not just download

Set `DELIVERY.json` `expect_audio: true` and `expect_music: true` by default.
New delivery plans must state `expect_music` explicitly; omission is rejected
unless the project is marked `legacy_project: true` (only for pre-music work).
Mount the exact `MUSIC.json` `asset.path` with `id="bgm-bed"`,
`data-timeline-role="music"`, one audio track, start 0, full edit duration and
the core timing attributes. Use a real `<audio>`, not a playback JS call.

Use `/hyperframes-audio` to duck/carve beneath the source voice. A prepared bed's
level is not the final mix target; adjust gain/envelopes by actual speech and
measure the encoded master around -14 LUFS integrated / ≤ -1 dBTP. Ensure music
does not mask consonants, start late, end early, click or restart at every scene.
SFX are a separate restrained layer. Music-led clips may use `/music-to-video`
for a beat grid; spoken words remain the primary timing authority for dialogue.

The finish gate re-reads `MUSIC.json` and the real HyperFrames timeline: the
`bgm-bed` clip must use the exact prepared file and cover the full edit, keep the
prepared source offset, a normal playback rate, readable automation and a
non-muted effective volume for at least part of the edit. It also rejects a
missing/silent/re-encoded bed and, for built-in downloads, an attribution,
license-evidence, catalog-record, original-audio or identity change. Master
loudness alone never proves music is audible: record whether you auditioned the
final mix (`listened`), measured it, or only inspected metadata. There is no
isolated music-stem render; do not claim one.

`finish.sh` validates the required licensed music hash/duration and actual
HyperFrames timeline use before render. QA stores the music identity and copies
credit text beside the candidate as `<slug>-music-credits.txt`. Review the final
mix and include these credits in the posting caption/description or in-video
credits as required. A sidecar alone does **not** satisfy attribution after upload;
make that requirement clear in the delivery note.

## 4. Other public sources and failure handling

If the built-in catalog has no fit, use public search/Agent-Reach to find music on
the composer's official site, Wikimedia Commons or another reputable source.
For each specific track verify commercial use **and synchronization/adaptation**
permission, download terms, required credits and any Content ID caveat. CC0 or
CC BY is the default; avoid NC/ND/SA or unclear licenses for an unknown destination.
“Royalty free”, “no copyright” or a download button alone is not a license.
Vocal checks are metadata only and singular/plural aware: declared voices, choirs
or sung descriptions are excluded unless negated (“without vocals”). A passing
search still means *metadata-inferred instrumental*, not an auditioned guarantee.

Prefer the authorized original audio URL. yt-dlp may retrieve a **specifically
licensed** track from a supported page if download terms permit; it does not
turn a YouTube/Instagram song into reusable music. No ripping trending reference
soundtracks, bypassing logins/captcha/rate limits or buying licenses silently.

An external/user-authorized asset needs the same `MUSIC.json` fields as built-in
output (ready status, choice reason, license + evidence, attribution, project-local
path/hash/duration, timeline_id bgm-bed) and normal decode checks. Do not label
external music CC BY unless the track's evidence actually says so.

Budget: one catalog query plus up to two refined/public searches and at most
three track downloads. If no suitable cleared music is obtainable, do not
silently deliver voice-only: report the blocker, or use an explicit user-approved
exception. For deliberate silence / authorized existing source music / requested
no-added-music set `expect_music: false` with `music_exception` in `DELIVERY.json`,
explain it in `MUSIC.md` and the final report. Existing old projects without the
new field retain their prior behavior.

No MusicGen installation is needed for downloading. Its default public weights
are CC BY-NC 4.0; do not treat it as a blanket commercially cleared fallback.
