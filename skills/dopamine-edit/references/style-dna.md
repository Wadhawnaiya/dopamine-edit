# Style DNA — mining the template library

The template library is
[yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos).
It is **not** a folder of downloadable templates. It is a changing prompt library
with live remake links where available. The prompt is the template: it describes the
visual system, the motion, the type, and the payoff. The poster and the Skillry
page are the visual reference.

## 1. What is on disk

`scripts/bootstrap.sh` clones it to:

```text
~/.cache/dopamine-edit/awesome-opus5-5-videos/
  data/videos.json          # 703 records
  prompts/<slug>.md         # full prompt + metadata, one per video
  README.md                 # curated highlights + categories
```

Each record in `data/videos.json`:

```json
{
  "slug": "ror-fly-880547",
  "author": "Ror_Fly",
  "author_url": "https://x.com/Ror_Fly",
  "post_url": "https://x.com/Ror_Fly/status/...",
  "category": "explainer",
  "tech_tags": ["canvas"],
  "prompt": "We're going to try a little test...",
  "prompt_partial": false,
  "poster_url": "https://media.skillry.dev/.../preview.webp",
  "skillry_url": "https://skillry.dev/ai-videos/opus-5-5/ror-fly-880547",
  "added": "2026-09-26",
  "has_remake": true
}
```

`has_remake: true` means a live, playable remake exists. Prefer those: you can
watch the motion instead of imagining it.

## 2. Category map

| Category | What it is good for | Use when |
|----------|---------------------|----------|
| `motion` (369) | Kinetic type, particles, abstract systems, transitions, logo stings | Default for short-form edits |
| `3d` (117) | Objects, environments, product turns, camera moves | Product, space, "impossible" scenes |
| `explainer` (116) | Diagrams, charts, maps, step-by-step motion | Data, how-to, story logic |
| `interactive` (101) | UI, game, cursor, web-like motion | UI motifs, screen-capture energy |

The curated README also groups them as Motion graphics / Explainers / 3D scenes
/ Games & interactive. Read it for the current highlights.

## 3. Tech tag map

These are the exact tags stored in `data/videos.json` (counts from the current
703-entry snapshot):

| Tag | Count | HyperFrames path | Notes |
|-----|-------|------------------|-------|
| `canvas` | 267 | 2D canvas in a sub-composition | Particles, trails, generative BG |
| `svg` | 183 | inline SVG + GSAP draw/morph | Crisp type, icons, diagrams, masks |
| `threejs` | 131 | Three.js adapter | 3D scenes, product turns, camera moves |
| `shader` | 92 | shader / WebGL | CRT, glitch, liquid, noise, displacement |
| `gsap` | 86 | default timeline | Best for seek-safe choreography |
| `css` | 57 | CSS keyframes / transitions | Cheap, deterministic, good for loops |
| `audio` | 39 | not visual | Beat-reactive ideas; audio is authored separately |
| `playable` | 22 | not visual | Interactive/game prompts; borrow only the motion |
| `particles` | 17 | canvas/Three particle system | Sparks, dust, confetti, data motes |
| `pixel` | 15 | canvas / CSS pixel filters | Retro, dither, pixel-art transitions |
| `webgl` | 9 | WebGL overlay | Shader-adjacent looks |
| `physics` | 9 | JS physics in canvas | Collisions, cloth, rigid bodies |
| `ai-image` | 6 | pre-rendered image assets | Generate stills, then animate them |

The matcher normalizes the friendly aliases `three` → `threejs` and `glsl` →
`shader`, so either spelling works on the command line.

If a prompt relies on a framework HyperFrames does not ship (`react-three-fiber`,
`p5`), translate the **motion idea**, not the code.

## 4. Scoring rubric

`match_style.py` ranks by:

- **Prompt keyword overlap** (weight 3×): subject nouns, mood, visual nouns,
  verbs. "neon", "particles", "blueprint", "shatter", "orbit", "chrome".
- **Category fit** (2×): default `motion`; `3d` for objects; `explainer` for
  data/steps; `interactive` only for UI.
- **Tech tag fit** (2× each): prefer `canvas`, `svg`, `gsap`, `css`, `threejs`,
  `shader`, `webgl`, `particles`.
- **Remake bonus**: `has_remake: true` +1.5.
- **Recency**: newer entries +0–1 (the library is updated regularly).
- **Penalty**: `prompt_partial: true` −1 (the prompt is incomplete).

The script returns `score`, `matched_terms`, and a `why` string. Trust the top
5, then choose by eye and by story — not by score alone.

## 5. How to choose compatible parents

Usually blend 2–3 compatible visual grammars. A coherent user-supplied reference
can suffice; do not add parents for a quota. Online references may supplement
the library: read `reference-research.md`, record provenance in `REFERENCES.md`,
then name exactly what is borrowed/changed in `STYLE.md`.

| Parent | Question it answers | What you take |
|--------|---------------------|---------------|
| **System parent** | What does the world look like? | Palette, type, texture, background system |
| **Moment parent** | What is the signature shot? | One transition, reveal, or camera move |
| **Sound/type parent** | What is the rhythm? | Cut cadence, caption treatment, SFX personality |

Examples:

- HUD Athlete = `3d` system (chrome/grid) + `motion` moment (freeze orbit) +
  `explainer` type (stat count-up).
- Glitch Confession = `motion` system (Vapor Terminal type) + `shader` moment
  (glitch slice) + `motion` captions (punch words).
- Product Deity = `3d` system (studio void) + `motion` moment (pop-out card) +
  `explainer` insert (spec callouts).

Prefer complementary ideas, not gratuitous runtime diversity. Three canvas
parents can look different; one good SVG/GSAP system can be enough. Add 3D or
shaders only when they improve the story and render reliably on this host.

## 6. Extract the DNA from a prompt

Read the full prompt and answer:

1. **Subject** — what is on screen, and what is the camera doing?
2. **Composition** — centered? grid? rule of thirds? full-bleed type?
3. **Palette** — named colors, materials, light temperature.
4. **Type** — face, weight, case, size relationship, placement.
5. **Motion grammar** — what moves, on what curve, on what beat?
6. **Texture** — grain, bloom, chrome, paper, CRT, glass, liquid.
7. **Transitions** — cuts, morphs, wipes, camera moves.
8. **Payoff** — the final reveal/loop. What is the "money shot"?
9. **Sound implication** — what would this world sound like?
10. **Transferable idea** — the one sentence you can apply to *this* footage.

If the prompt is only a topic ("make a video about X"), it is not a visual
template. Skip it; find one with a described look.

## 7. `STYLE.md` template

Write this into `output/<slug>/STYLE.md`:

```markdown
# STYLE — <slug>

## Source read
- Subject:
- Energy:
- Story in one line:
- Payoff:
- Constraint:

## Parents
1. **System** — `<slug>` (<category>, <tags>) — <skillry_url>
   Borrowed: <palette / type / texture / bg system>
2. **Moment** — `<slug>` — <skillry_url>
   Borrowed: <the one shot/transition>
3. **Sound/type** — `<slug>` — <skillry_url>
   Borrowed: <cadence / caption / SFX personality>

## Visual system
- Palette: `<hex>` bg, `<hex>` ink, `<hex>` accent, `<hex>` support
- Type: `<display>` + `<accent>`
- Texture: <grain/bloom/chrome/paper/CRT>
- Composition: <centered/grid/split/full-bleed>
- Camera: <locked/push/orbit/handheld>

## Motion grammar
- Cut cadence:
- Signature move:
- Transition set:
- Pattern interrupts (rotate 3):

## Sound
- BPM / mood:
- Hit layer:
- Voice treatment:

## 3 signature moments (storyboard)
1. Hook —
2. Mid pattern-break —
3. Payoff —

## Not borrowing
- <things from the parents that do not fit this footage>

## Originality check
- This is a new piece for <subject>; the parents are grammar, not content.
```

## 8. If the library is unavailable

Use this built-in taxonomy and pick by feel:

| Footage | System | Moment | Type |
|---------|--------|--------|------|
| Person talking | Vapor Terminal / Paper Punch | text-behind-subject | Punch captions |
| Fitness / sport | Acid Lab / Blood Sport | freeze + orbit | HUD stats |
| Product / fashion | Chrome Heat | pop-out card | Chrome display |
| Travel / mood | Deep Sea | light leak + push-in | Minimal |
| Data / explainer | Paper Punch | chart hit | Kinetic type |
| Comedy / vlog | Paper Punch + acid | sticker slap | Sticker captions |

The built-in taxonomy is enough to ship; the library makes it fresher.

## 9. Using the posters

`match_style.py --download-posters <dir>` saves the poster WebP for each pick.
Read them with the image reader and make a 3-up moodboard. Use them to decide
**palette and texture**, not to copy a frame. Posters are reference material;
do not republish them in the deliverable.

## 10. Legal and ethical note

- Check the cached repository's current license. A code/prompt license does not
  automatically license linked videos, logos, music or people. Borrow visual
  grammar rather than copying a creator's exact composition/brand/footage.
- Do not download and re-upload someone else's video as your own.
- A user-supplied local reference/link does not itself establish ownership or
  reuse rights. Keep it inspiration-only unless permission/license is known.
