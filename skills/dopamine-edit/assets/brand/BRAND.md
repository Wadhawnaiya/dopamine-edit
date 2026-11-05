# Brand asset — "A Dhurandhar" neon sign

Owned by the skill owner; used as the always-on brand layer for their videos.

- `logo.png` — transparent cutout produced by `scripts/brand-cutout.sh`
  (ImageMagick `luminance × saturation` key, recipe v1), trimmed with 24 px
  transparent padding. **Ships with the skill** so the brand gate works out of
  the box.
- `logo.json` — source and asset hashes, dimensions, alpha coverage and the
  exact recipe.
- `bg.jpg` — the original photo. **Not committed** (it contains the owner's room,
  not just the sign); it lives in the owner's footage workspace at
  `reference/bg.jpg`. Rebuild the cutout from it, or from your own newer photo.

The dark curtain background is removed; the acrylic mount, brackets and tube
glow remain as part of the sign. Do not edit `logo.png` by hand. After any
rebuild, run `brand.py install` in each project and rerender.

Behaviour, mounting rules and the delivery gate: `references/brand-layer.md`.
