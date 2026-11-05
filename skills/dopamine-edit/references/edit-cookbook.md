# The Dopamine Edit — creative doctrine

This is the taste layer. It assumes the technical contracts come from
`/hyperframes-core`, `/hyperframes-animation`, and `/hyperframes-registry`.

The goal is not "a video with effects". The goal is a clip a stranger watches
three times: a hook they cannot scroll past, a rhythm that keeps promising the
next frame, and a payoff that makes the loop feel intentional.

**Priority:** `SKILL.md` owns scope, truth, timing and delivery gates. The recipes
below are a taste library, not a quota of cuts, inserts, glitches or SFX. Preserve
complete thoughts, native-script captions, intentional pauses and readability.
Do not invent a statistic to fill a recipe. Reference sourcing/provenance lives
in `reference-research.md`; measured delivery checks live in `quality-gates.md`.

---

## 1. The dopamine equation

```text
TENSION -> RELEASE -> NEW TENSION -> BIGGER RELEASE -> LOOP
```

Aim for meaningful evolution roughly every 2–3 seconds, such as:

- **a question** ("what is this?"),
- **a pattern break** (something new enters),
- **a reward** (a satisfying hit, reveal, or match cut),
- **a near-miss** (almost resolved, not yet).

Do not manufacture anxiety or interrupt an important sentence solely for pace.

A cut is not a reward by itself. A cut **into a new visual idea** is.

### The 5-beat spine (short-form, 6–15 s)

| Beat | Time | Job | Visual |
|------|------|-----|--------|
| Hook | 0.0–1.0 s | Stop the scroll | Strongest frame + 1–3 word text + impact |
| Context | 1.0–3.0 s | Orient | Subject + one-line premise |
| Escalation | 3.0–8.0 s | Promise more | 3–5 beats, each a new visual event |
| Payoff | 8.0–12.0 s | Deliver | Freeze/orbit/slow-mo + the money graphic |
| Close | 12.0–15.0 s | Loop or question | Match the first frame or ask |

For 30–60 s, repeat escalation in 3 acts; keep the same hook and close.

---

## 2. The layer stack

Build in this order. Every layer is a track (or a group of tracks). The subject
sits **between** the mid graphics and the foreground, not on top of everything.

```text
05  foreground FX   grain, scanlines, glitch, light leak, UI chrome, vignette
04  subject         cut-out webm (or masked full-frame footage)
03  mid graphics    headline, stats, arrows, labels, lines, diagrams
02  environment     grid, gradient, particles, 3D set, moving background
01  plate / bg      plate.webm, generated background, or blurred source
00  audio           voice, music bed, SFX (not a visual track)
```

Why this order matters: a headline that passes **behind** the subject's
shoulder creates depth. A headline slapped on top of the face looks like a
subtitle. Depth is the difference between "edited" and "expensive".

### HyperFrames mapping

- plate / environment / mid / subject / FX / captions are separate timed clips
  on separate tracks (`data-track-index`).
- The cut-out `<video>` goes inside a plain wrapper `<div>`; animate the
  wrapper's opacity, never the timed video.
- Foreground FX is usually a non-timed overlay owned by CSS/GSAP, or a timed
  clip with `pointer-events: none`.
- Captions live on their own top track so they never fight the subject.

---

## 3. Hooks that work (visual, not verbal)

Pick one and shoot the first frame for it:

1. **Mid-action start** — the clip begins at the most violent/energetic moment.
2. **Payoff first, then rewind** — show the result, then "here's how".
3. **Impossible scale** — subject tiny in a huge graphic environment.
4. **Face + 2-word accusation** — "STOP DOING THIS" over a reaction.
5. **Object in the wrong place** — a product floating in space, a person in a
   HUD, a shoe on a planet.
6. **Countdown / number** — "3", "1", "$0" as a full-frame hit.
7. **Before/after split** — one frame, two states, hard line between.
8. **Glitch reveal** — the subject "breaks" into pixels, then reassembles.
9. **Text-behind-subject** — the headline is occluded by the person; the brain
   leans in to read it.
10. **Sound-first** — a whoosh/impact lands before the image resolves.

Never open with: a logo, a fade from black, a slow pan, a title card that says
the video's name, or a talking head at rest.

---

## 4. Pacing and rhythm

### Cut rhythm

| Section | Average shot | Pattern |
|---------|--------------|---------|
| Hook | 0.4–0.8 s | 2–3 micro-cuts, each a new angle/graphic |
| Context | 0.8–1.5 s | 2 shots, one caption group each |
| Escalation | 0.5–1.2 s | cut on every beat, new graphic each time |
| Payoff | 1.5–3.0 s | hold the money shot; motion inside the frame |
| Close | 0.8–1.5 s | one clean button, loopable |

### Speed ramps

- 2–4× through a transition (whip, whip-pan, zoom blur).
- 0.4–0.6× on impact (freeze the peak, then release).
- Keep pitch-preserved audio for voice; mute ramped B-roll audio.

### Pattern interrupts (rotate, do not repeat the same one)

punch-in · punch-out · whip pan · zoom blur · freeze + orbit · color invert ·
restrained color accent · split screen · object wipe · text wipe · glitch slice · speed ramp ·
hard cut to insert · match cut · silhouette cut · negative space reveal.

### The 3-second test

Review every 3-second window. If nothing changes, ask whether a meaningful hold
serves the thought/payoff. If not, tighten it or add an informative visual move.
Avoid rapid strobing or repeated large-area high-contrast flashes.

---

## 5. Six dopamine palettes

Use one palette per video: one background, one ink, and at most two accents
(the accent + support slots).

### 1. Acid Lab (high-energy tech / fitness / streetwear)

```text
bg      #050505
ink     #F5FF00   acid yellow
accent  #FF2E88   hot magenta
support #00E5FF   cyan
```

### 2. Chrome Heat (automotive / luxury / product)

```text
bg      #0A0A0C
ink     #F2F2F2
accent  #FF4D00   signal orange
support #8A8F98   brushed steel
```

### 3. Vapor Terminal (AI / code / cyber)

```text
bg      #070312
ink     #E8E6FF
accent  #B026FF   violet
support #00FFC8   mint
```

### 4. Paper Punch (editorial / explainer / lifestyle)

```text
bg      #F4F0E6
ink     #111111
accent  #FF3B30   red
support #1F5EFF   blue
```

### 5. Deep Sea (calm / cinematic / documentary)

```text
bg      #04121A
ink     #E6F7FF
accent  #4DE1C1   aqua
support #FFB86B   sand
```

### 6. Blood Sport (sports / drama / challenge)

```text
bg      #0B0000
ink     #FFFFFF
accent  #E10600   racing red
support #FFC400   warning yellow
```

Contrast rule: body text must hit WCAG AA at phone size; display text can be
bigger but never thinner than 600 weight on a busy frame. Add a 1–2 px dark
stroke or a soft shadow when text crosses footage.

---

## 6. Type system

**Pairing:** one display face + one mono/sans accent.

| Role | Recommended | Fallback |
|------|-------------|----------|
| Display | Anton, Archivo Black, Bebas Neue, Oswald 700 | Inter 900, Montserrat 900 |
| Accent / data | JetBrains Mono, IBM Plex Mono, Space Mono | Inter 600 |
| Caption | Inter 800, Manrope 800 | system sans 800 |

Rules:

- Usually 2–5 words per caption group; 2 lines max; single words for accents.
- Latin display type can use uppercase/tight tracking; preserve natural case and
  shaping for native scripts. Verify Devanagari glyphs and conjuncts locally.
- Highlight **one** keyword per group in the accent color; do not rainbow.
- Numbers are heroes: 2–3× the size of the label, mono or display, counted up.
- Start with 8% top/left, 15% right, 18% bottom safe margins; check target UI.

---

## 7. Cut-out recipes (the signature move)

These assume `subject.webm` + `plate.webm` from
`hyperframes remove-background`.

### A. Text-behind-subject (the workhorse)

```text
plate.webm (bottom)
headline / stat (mid, oversized, crosses the body)
subject.webm (top)
grain + vignette (foreground)
```

The headline must physically overlap the silhouette. Animate the headline
from behind the shoulder: start offset, slide through, settle. Add a soft
drop shadow to the subject so it separates from the type.

### B. HUD sandwich (sci-fi / fitness / tech)

```text
plate.webm
animated grid + rings + ticker (environment)
subject.webm
scanlines, corner brackets, targeting reticle (foreground)
```

Keyframe a decorative target marker only when it supports the visual language;
do not imply a measured tracking statistic. Use glitch sparingly, not every cut.

### C. Pop-out card (product / fashion / reveal)

```text
blurred, scaled source (background)
rounded card / color block (mid)
subject.webm scaled 1.05 (top), drop shadow
```

The subject breaks the card's edge. Animate the card's scale from 0.9 to 1.0
with a 0.15 s overshoot; the subject follows 2 frames later.

### D. Freeze + orbit (payoff)

Freeze the peak frame, duplicate the plate and subject, then:

- slow 1.02→1.10 scale on the subject,
- 3–5° rotation,
- parallax the plate opposite the subject,
- particles/dust in front,
- one impact hit at the freeze.

This is the cheapest "expensive" shot in the toolkit.

### E. Split diopter (interview / explainer)

Subject on the left 55%, graphics on the right 45%, a hard vertical line
between. The subject's edge can bleed over the line by 2–4%. Use for stats,
lists, comparisons, and "3 things" formats.

### F. Echo / trail (music / sport)

Duplicate the subject 3–5 times, offset in time and position, lower opacity,
tint each copy toward the accent. The newest copy is full color. Use on a beat.

### G. Silhouette reveal (dramatic / cinematic)

Subject starts as a solid accent-color silhouette (threshold/flood), then the
color drains to reveal the real footage. Pair with a riser and a hard impact.

### H. Object tunnel (3D / product)

Put the subject (or a cut-out product) inside a generated 3D tunnel/portal.
Camera pushes through on the beat. Use a registry block or a Three.js
sub-composition; do not fake 3D with 2D scale alone.

---

## 8. Full-frame graphic inserts

Inserts are usually 0.8–2.0 s graphic scenes between live-action beats. Aim for
two in a 12–30 s edit when they explain something; fewer/none for short or dense
dialogue. Keep speech continuous beneath visual inserts where appropriate.

| Insert | Job | Motion |
|--------|-----|--------|
| Stat hit | Make a number land | Count-up + scale punch + impact |
| Kinetic type | Say the thesis | Word-by-word mask reveal, 0.08 s stagger |
| Chart hit | Show the change | Bars/lines draw on, axis labels pop |
| Map zoom | Locate the story | Country highlight, fly-to, pin drop |
| 3D object | Make it tangible | Turntable, explode view, orbit |
| Logo sting | Brand the moment | Mark draw-on + shine sweep + hit |
| Comparison | Before/after | Split wipe with a hard edge |
| Quote card | Authority | Type-on + underline + subtle drift |

Cut **into** an insert on motion (whip, shape match, color match), not on a
static frame. Cut **out** of an insert on a hit or a match cut back to the
subject's eyeline.

Use `/motion-graphics` for the insert's own build. Keep inserts visually
distinct from the live-action grade: either fully graphic (flat/BW/brand) or
fully in-world (HUD/hologram).

---

## 9. Transitions

Ranked by energy:

1. **Hard cut on action** — default; free, invisible, best.
2. **Whip pan / zoom blur** — 4–8 frames, whoosh.
3. **Match cut** — shape, color, or motion carries the eye.
4. **Object wipe** — subject/product passes camera, reveals next scene.
5. **Glitch slice** — 2–3 frames, RGB split, digital SFX.
6. **Light leak** — restrained accent, never repeated large-area strobing.
7. **Mask reveal** — circle/bar/type expands to reveal.
8. **Crossfade** — only for time passage or dream states; never as default.

Search the registry first:
`npx hyperframes catalog --query "whip pan transition" --json`.

---

## 10. Sound design

### Speech first

When anyone speaks, run Whisper before you place a single sound effect:

- the transcript finds the hook line, the best 6–15 s soundbite, and the exact
  cut points;
- captions inherit word timing **retimed through the edit map**; verify sync
  after cuts, reorderings, freezes and speed changes;
- whooshes land on speech cuts, impacts on the first word of a new idea, and
  pops on caption groups — never mid-word;
- silences longer than 0.4 s are review candidates, not automatic deletion.

Whisper transcribes; it does not clean audio. Fix noise with `/media-use` and
mix with `/hyperframes-audio`.

### The bed

- 120–140 BPM for energy; 90–110 for cinematic; 140–160 for sport/chaos.
- Pick a track with a clear downbeat and a drop you can put the payoff on.
- Run `npx hyperframes beats` to get the grid; cut on beats, not on vibes.

### The hit layer

| Event | Sound | Peak level |
|-------|-------|-------|
| Cut / transition | whoosh (0.2–0.5 s) | -20 dBFS |
| Impact / freeze | bass impact | -14 dBFS |
| Text appearance | pop / click / type | -26 dBFS |
| Riser into payoff | riser (1–2 s) | -20 dBFS |
| Glitch / digital | glitch | -18 dBFS |
| Reveal / sparkle | sparkle / chime | -20 dBFS |
| End / logo | chime / impact | -16 dBFS |

These are ceilings for a dialogue-led edit, not targets to reach: keep every hit
at least 12–18 dB below the voice in that moment, and quieter when unsure.

Bundled SFX live in
`~/.config/opencode/skills/media-use/audio/assets/sfx/`.

### The mix

- Voice is the loudest element and must stay effortless to follow; -16 to -12
  LUFS short-term is a guide.
- Music under voice: **-30 to -36 LUFS** (18–24 dB below the voice), high-passed
  at 120 Hz, carved at 2–4 kHz with `/hyperframes-audio` (`carve.mjs`) and ducked
  6–12 dB. A volume duck alone is not a mix, and a bed near voice level is a bug.
- SFX: peaks 12–18 dB below the voice (see the table); never mask a consonant.
- Master: measure the final encoded mix, about -14 LUFS integrated, ≤ -1 dBTP,
  and keep a clear loudness contrast between speech and the bed.
- Reinforce meaningful actions; do not layer whooshes/pops on every cut/word.
- Silence is a tool: 0.2 s of silence before a payoff makes it twice as loud.

---

## 11. Caption styles

Word timing comes from the Whisper transcript (`scripts/transcribe.sh`), never
from guessing or from the platform's auto-captions.

| Style | Look | Use |
|-------|------|-----|
| **Punch** | One word at a time, huge, centered, scale-pop | High energy, hooks |
| **Stack** | 2–4 words, bottom-left, accent keyword | Talking head, explainer |
| **Karaoke** | Full line, active word fills accent | Music, rap, chant |
| **HUD** | Mono, bracketed, type-on | Tech, sci-fi, data |
| **Sticker** | Rotated card, drop shadow, hand-placed | Collage, lifestyle |
| **Minimal** | Small, clean, bottom, no background | Cinematic, documentary |

Usually 2–5 words per group with readable holds and output-time word timing.
Never split a name/number, cover mouth/eyes, or force an unreadable minimum
duration; test at phone size. Correct ASR against the recording before styling.

---

## 12. Color and texture

- **Grade first, then style.** Fix exposure/white balance before adding a look.
- Use `/media-use` treatments for canonical looks; do not stack random CSS
  filters.
- Safe texture stack: slight contrast S-curve, 5–10% bloom, 3–8% grain,
  vignette 10–20%, chromatic aberration 0.5–1.5 px on edges only.
- Keep skin tones believable. If the grade turns skin green, it is wrong.
- Inserts can be more stylized than live action; the contrast is the point.

---

## 13. Format recipes (pick one per clip)

### 1. The HUD Athlete (fitness / sport / dance)

HUD sandwich, stat hits for speed/reps/time, impact on every landing, 130–150
BPM, punch captions. Payoff: freeze + orbit + final stat.

### 2. The Product Deity (product / fashion / tech)

Pop-out card + 3D tunnel + chrome type, macro inserts, riser into a hero turn,
clean impact on the logo. Palette: Chrome Heat.

### 3. The Glitch Confession (talking head / storytime)

Text-behind-subject hook, glitch slices on the reveals, split diopter for the
"before/after", minimal captions, one big stat. Palette: Vapor Terminal.

### 4. The Data Drop (explainer / finance / business)

Paper Punch, kinetic type thesis, 3 chart hits, split diopter, one map zoom.
Every number counts up. Calm but relentless.

### 5. The Collage Chaos (lifestyle / comedy / vlog)

Sticker captions, paper cut-outs, object wipes, freeze-frame doodles, SFX pops.
Palette: Paper Punch + one acid accent. Keep the subject's face clean.

### 6. The Cinematic Loop (travel / mood / brand)

Deep Sea, slow push-ins, light leaks, one huge title, ambient bed, hard loop
on the first frame. Minimal captions; let the image breathe and preserve a
purposeful hold. Movement should serve the image rather than a cut quota.

### 7. The Countdown (challenge / listicle / ranking)

Full-frame numbers 3-2-1, each with a different environment, subject cut out and
dropped into each, impact on every number, payoff at #1.

### 8. The Before/After (transformation / repair / makeup)

Split screen, hard wipe, match cut on the same pose, stat hit for the delta,
freeze on the after. No music dip; drive through the reveal.

---

## 14. Do not ship

- fade from black, logo intro, or 2 s of dead air at the start;
- a static talking head with captions only;
- 6 fonts, 9 colors, or 3 competing effects in one frame;
- text over the mouth/eyes, text in the platform UI zone, or text smaller than
  24 px at 1080p;
- a matte seam, halo, or cut-out that clips hair/fingers;
- a music bed that buries the voice;
- a crossfade as the default transition;
- an effect that does not serve the story (particles for particles' sake);
- a payoff that never arrives;
- an outro longer than 1 s.

---

## 15. The 10-second director's check

Before rendering, watch the first 10 seconds with the sound on and answer:

1. Would I stop scrolling in the first second? Why?
2. What is the promise of the next 5 seconds?
3. Where is the first genuine surprise?
4. Is there any 3-second window with no change?
5. Does the subject feel inside the world or pasted on top?
6. Is the type readable at 25% size?
7. Does sound support the important actions without masking speech?
8. Is the payoff bigger than the hook?
9. Does the last frame loop or ask?
10. What would I cut?

If you cannot answer 1, 3, and 8 with a specific frame, the edit is not done.
