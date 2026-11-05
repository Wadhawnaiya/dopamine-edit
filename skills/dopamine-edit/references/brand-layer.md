# Brand layer — the always-on neon sign

Every dopamine-edit video carries the channel's brand mark: the transparent neon
sign cut out from the owner's photo (`reference/bg.jpg`). It is a **permanent
brand layer**, not an optional decoration. Only an explicit user instruction for
a given edit removes it.

## Asset

| File | Role |
| --- | --- |
| `<skill>/assets/brand/bg.jpg` | Original photo (ownership: the skill owner). Never edited in place. |
| `<skill>/assets/brand/logo.png` | Transparent cutout used in videos (RGBA, trimmed, 24 px padding). |
| `<skill>/assets/brand/logo.json` | Recipe, source/asset SHA-256, size, alpha coverage. |
| `<skill>/assets/brand/BRAND.md` | This asset's provenance and rebuild instructions. |

The cutout is produced by a deterministic ImageMagick key on `luminance ×
saturation`: bright saturated neon survives, the dark curtain does not. The
acrylic mount and tube glow stay attached to the sign; that is intended. The
photo is the owner's own brand asset, so it is licensed for these videos — do not
substitute downloaded look-alike logos, and do not run a subject/user matte on
it (`matte.sh` targets people, not logos).

Rebuild only when the source or recipe changes:

```bash
bash "$SKILL_DIR/scripts/brand-cutout.sh" /path/to/bg.jpg --outdir "$SKILL_DIR/assets/brand"
```

Rebuilding changes `logo.png`, so every open project must reinstall
(`brand.py install`) and rerender. Do not hand-edit `logo.png`.

## Install into a project

After scaffolding and before assembling the timeline:

```bash
python3 "$SKILL_DIR/scripts/brand.py" install --project "$OUT/project"
```

This copies the exact skill asset to `project/assets/brand/logo.png` and writes
`project/assets/brand/BRAND.json` with its hash. If the project holds a different
image under that path, the command refuses instead of overwriting it.

## Mount on the timeline

A plain `<img class="clip">` at the composition root, full duration, on its own
graphics track above the video and below captions/text:

```html
<img id="brand-layer" class="clip" src="assets/brand/logo.png" alt=""
     data-start="0" data-duration="TOTAL_SECONDS" data-track-index="1"
     style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.28" />
```

- `id` must stay `brand-layer`; the gate matches the id **and** the exact `src`.
- Start at `0` and end at the full composition duration, in **every** scene
  arrangement — one root-level clip covers nested scenes.
- Default treatment is a dimmed backdrop (`opacity` about `.15`–`.4` over dark
  footage, higher on dark plates) so dialogue captions stay readable. A bright
  full-opacity lockup is allowed for intros, outros and title cards.
- Keep captions and key text on tracks above it. Never let the sign sit over a
  face at high opacity or animate it in a way that flashes.
- Motion, if any, must be seek-safe and slow (drift, breathing glow) — no jump
  cuts that restate at each scene boundary.

## Gate

Set `expect_brand: true` in `DELIVERY.json` (the default for new edits). With it,
`finish.sh` refuses to accept a candidate unless:

- `project/assets/brand/logo.png` exists, is inside the project, matches
  `BRAND.json`, and byte-matches the current skill asset;
- the HyperFrames timeline has a `brand-layer` clip with the exact brand `src`;
- that clip has resolved timing (`pendingReason`/`laneError` clear) and covers
  the whole edit.

`expect_brand: false` is an explicit, per-edit opt-out (for example when the user
asks for a clean unbranded export); it must be deliberate, not a leftover. A
project created before brand gating may set `legacy_project: true` to omit the
field, but new projects must state it.

## Replacing the brand image

Point the owner at a new source photo, keep the same filename conventions, run
`brand-cutout.sh`, verify the cutout visually over dark and light plates, then
reinstall and rerender affected projects. Never silently swap the asset for one
with a different hash while a candidate is pending review.
