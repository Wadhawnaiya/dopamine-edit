# Preview checkpoint — show the draft before the delivery render

The user wants to see and redirect the edit **before** it is rendered at delivery
quality. Default workflow: build → preview → user reviews → apply changes →
delivery render. This is an approval stop, not a routine question: present the
draft and ask what to change; do not render delivery first and ask afterwards.

## Run it

```bash
bash "$SKILL_DIR/scripts/preview.sh" "$OUT/project" "$SLUG" --json
```

It renders a **draft** (fast, proxy quality) of the current composition and
copies the artifacts to `$OUT/preview/`:

| Artifact | Use |
| --- | --- |
| `<slug>-preview.mp4` | Watch end to end: pacing, hook, captions, matte, mix |
| `<slug>-cover.jpg` | First frame / thumbnail framing |
| `<slug>-contact.jpg` | Contact sheet of proof frames |
| `<slug>-preview-qa.json` | Automated checks and loudness of the draft |
| `frames/` | Individual proof frames for close-ups |
| `PREVIEW.json` | Recorded digest, status `awaiting_review` |

It never writes to `final/`, never marks the source processed, and is safe to run
repeatedly. Draft renders reuse `finish.sh --draft`, so the same composition,
music, brand and QA gates run — a draft that fails a gate is a real defect, not a
preview quirk.

## Present it to the user

- Show the MP4 path and, when the client can render images, the cover and contact
  sheet so they can see framing, captions and matte edges without leaving chat.
- Offer the Studio preview for an editable surface: `preview.sh` prints the exact
  command (`<CLI> preview <project>`). Do not start a server unprompted.
- State that the draft is a proxy: quality/encoding differ from delivery, but
  timing, layout and audio balance are representative.
- Ask a focused question: what to change (hook, pacing, captions, music level,
  brand opacity, colours), not "is it okay?".

## Apply changes, then approve

Edit the composition and run `preview.sh` again — the record and digest update, so
the previous approval is invalid on purpose. When the user approves:

```bash
python3 "$SKILL_DIR/scripts/preview.py" approve --root "$OUT" --note "approved: tightened hook"
```

Then run the delivery render:

```bash
bash "$SKILL_DIR/scripts/finish.sh" "$OUT/project" "$SLUG" --json
```

## The gate

`finish.sh` refuses a **delivery** render unless the approval digest matches the
current composition (`PREVIEW.json` + `APPROVED.json`):

| State | Meaning | Action |
| --- | --- | --- |
| `missing` | no preview recorded | run `preview.sh` |
| `awaiting_review` | preview recorded, not approved | present it, then approve |
| `changed` | composition edited after approval | preview again, then approve |
| `approved` | matches current composition | delivery allowed |

`preview.py verify --root "$OUT"` reports the state; `preview.py status` also
prints both records. `approve` refuses a changed composition unless `--force`,
which is only for a user who explicitly approved the edited state without a new
draft.

## Unattended runs

`DOPAMINE_SKIP_PREVIEW=1` bypasses the checkpoint for an explicitly unattended
run (the installed watcher service sets it). Do not use it on a normal request;
the whole point is that the user sees the cut first. Never set it merely to clear
an error.
