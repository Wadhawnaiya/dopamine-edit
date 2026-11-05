# Dopamine Edit

A reusable agent skill for footage-led HyperFrames video editing: transcript-led
cuts, captions, layered motion graphics, licensed background music, and measured
delivery checks.

## What it does

1. Understands your footage and verifies important speech before designing cuts.
2. Chooses a visual system from local references, prompt templates and optional
   web/social research through Agent-Reach and yt-dlp.
3. Writes a music brief from the actual story, emotion, speech density and length.
4. Searches public licensed instrumental music, downloads a selected track and
   prepares a trimmed/faded local bed with license evidence and credit text.
5. Mounts the bed in the composition and mixes it under dialogue.
6. Checks the composition, encoded video/audio, required music timeline,
   dimensions/FPS/duration, loudness and review evidence before marking done.

This is an **agent workflow**, not an unattended all-in-one video-editor binary.
An agent performs creative decisions and calls the bundled deterministic helpers.
Virality and flawless output are not guaranteed. Platform access, model accuracy
and reference licenses still need case-by-case review.

## Install the custom skill

Linux is the supported platform (Bash, Python 3.10+, FFmpeg/FFprobe, Node.js 22+
and git). The watcher is an optional Linux/systemd feature, disabled by default.

```bash
git clone https://github.com/Wadhawnaiya/dopamine-edit.git
cd dopamine-edit
bash scripts/install.sh
```

The installer copies only `skills/dopamine-edit` to
`~/.config/opencode/skills/dopamine-edit`. Existing installations are backed up
before replacement; it does not install media models, change credentials, run
footage jobs or start services. OpenCode watches saved skill files; `/reload`
can force discovery if needed.

For another compatible agent, copy the same skill folder into that agent's skill
directory, or set `DOPAMINE_SKILLS_DIR` when invoking the installer.

## Workflow dependencies

The upstream HyperFrames skills and Agent-Reach are **not vendored here**. Install
them from their official projects under their own terms. On this development
machine the audio skills were already installed; the HeyGen helper was installed
separately. This repository does not imply they are installed on your machine.

Core HyperFrames skill pack, then the owning workflows used by this skill:

```bash
npx hyperframes@0.9.15 skills update
npx hyperframes@0.9.15 skills update general-video hyperframes-audio music-to-video
```

Read the skill's **Load the contracts** section for conditional caption, keyframe,
overlay and motion-graphics skills. Official setup/help takes precedence if a
future CLI changes these commands. Optional research dependency:
[Agent-Reach](https://github.com/Panniantong/Agent-Reach); `yt-dlp` handles
supported public reference downloads. Respect login/captcha/rate-limit boundaries.

Background-music downloads use Python's standard library and FFmpeg/FFprobe.
**No HeyGen login, GPU, PyTorch, MusicGen or API key is needed** for the built-in
public music path. Optional HeyGen catalog/generation support needs the
[official helper](https://developers.heygen.com/cli) and your own sign-in.
No paid generation is enabled by this repository.

## Use

```bash
export DOPAMINE_ROOT="$HOME/Work/video_editing"
export DOPAMINE_HF_VERSION=0.9.15
mkdir -p "$DOPAMINE_ROOT/raw"
```

Put source videos in `raw/`, then ask your agent:

> Use @dopamine-edit to edit the pending footage. Understand it first, download
> suitable licensed background music, and mix it under the original speech.

The default root is `~/Work/video_editing`; `DOPAMINE_ROOT` overrides it. Raw
media is read-only. Outputs are separate revision directories. A request to
change the skill does **not** process footage.

Useful helpers:

```bash
bash ~/.config/opencode/skills/dopamine-edit/scripts/bootstrap.sh
python3 ~/.config/opencode/skills/dopamine-edit/scripts/music.py --help
python3 skills/dopamine-edit/scripts/test_pipeline.py
```

## Music and attribution

The built-in provider is Kevin MacLeod's public Incompetech catalog. The downloader
checks its current CC BY 4.0 declaration and retains the selected catalog record,
license-page evidence, original audio, prepared bed, hashes and credit text in
the **video project's output**, never this repository.

Track matching ranks metadata; it is not a claim that the agent listened to music.
Final review distinguishes playback review from measurements-only review.

Carry `<slug>-music-credits.txt` into the platform's caption/description or other
appropriate credits. Keeping a local sidecar alone does not satisfy attribution
when publishing a video. No track is guaranteed Content-ID-claim-free. Public
access or “royalty-free” wording is not a universal license.

No music, raw footage, model weights, reference-library content, tokens, account
sessions or third-party skill source is distributed here. External tools,
catalogs, music, fonts and templates retain their own licenses. Public repository
visibility by itself does not grant rights to those dependencies/assets.

## Tests and limits

The regression suite uses synthetic media, isolated state and controlled CLI
stand-ins. It covers real FFmpeg encode/decode and music preparation, failed
checks, missing/unmounted/changed music, silent audio, dimensions, safe rerenders,
source identity, caption-engine arguments and output protection. It does not
claim to test every website, ASR/matting model or creative outcome.

A real local HyperFrames smoke render and a licensed music download were also
checked during development; generated test media is intentionally excluded.

Detailed workflow: [`skills/dopamine-edit/SKILL.md`](skills/dopamine-edit/SKILL.md).
