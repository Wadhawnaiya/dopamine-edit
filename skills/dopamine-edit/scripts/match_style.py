#!/usr/bin/env python3
"""Rank templates from awesome-opus5-5-videos for a piece of footage.

The library is a set of executable prompts, not video files. This script
returns the prompts whose visual grammar best matches a query, plus links to
the live remake and poster.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_REFS = Path(os.environ.get('DOPAMINE_CACHE_DIR', str(Path.home() / '.cache/dopamine-edit'))) / 'awesome-opus5-5-videos'

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "with", "video",
    "make", "create", "animation", "animate", "style", "like", "using", "use",
    "should", "would", "could", "show", "showing", "full", "very", "really",
}

# The library tags are not the same words the docs use: it stores `threejs`,
# `shader`, `webgl`, `pixel`, etc. Accept the friendly names and normalize them
# so a query for "three" still hits a `threejs` record.
TAG_ALIASES = {
    "three": "threejs",
    "three.js": "threejs",
    "threejs": "threejs",
    "glsl": "shader",
    "shader": "shader",
    "shaders": "shader",
    "webgl": "webgl",
    "particles": "particles",
    "particle": "particles",
    "canvas": "canvas",
    "svg": "svg",
    "gsap": "gsap",
    "css": "css",
    "audio": "audio",
    "playable": "playable",
    "pixel": "pixel",
    "physics": "physics",
    "ai-image": "ai-image",
}

PRESETS = {
    "hud-athlete": {
        "query": "hud athlete fitness tracker speed lines impact freeze orbit stat",
        "category": "motion",
        "tags": ["canvas", "gsap", "particles", "svg"],
    },
    "product-deity": {
        "query": "product turntable chrome studio orbit explode macro",
        "category": "3d",
        "tags": ["threejs", "shader", "gsap"],
    },
    "glitch-confession": {
        "query": "glitch portrait kinetic type confession rgb split scanline",
        "category": "motion",
        "tags": ["shader", "canvas", "svg"],
    },
    "data-drop": {
        "query": "data chart map explainer count up diagram",
        "category": "explainer",
        "tags": ["svg", "gsap", "canvas"],
    },
    "collage-chaos": {
        "query": "collage sticker paper cutout scrapbook doodle",
        "category": "motion",
        "tags": ["svg", "css", "canvas"],
    },
    "cinematic-loop": {
        "query": "cinematic loop light leak film grain title atmosphere",
        "category": "motion",
        "tags": ["css", "shader", "canvas"],
    },
}


def normalize_tag(tag: str) -> str:
    key = tag.strip().lower()
    return TAG_ALIASES.get(key, key)


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9+#.-]*", text.lower())
    return [w for w in words if len(w) > 1 and w not in STOP]


def load_library(refs: Path) -> list[dict]:
    data = refs / "data" / "videos.json"
    if not data.exists():
        raise SystemExit(
            f"template library not found at {data}\n"
            "run: ~/.config/opencode/skills/dopamine-edit/scripts/bootstrap.sh"
        )
    with data.open() as f:
        items = json.load(f)
    if not isinstance(items, list):
        raise SystemExit(f"unexpected videos.json shape in {data}")
    return items


def score_item(item: dict, query_tokens: list[str], category: str | None,
               tags: list[str]) -> tuple[float, list[str]]:
    prompt = (item.get("prompt") or "").lower()
    cat = (item.get("category") or "").lower()
    item_tags = [str(t).lower() for t in (item.get("tech_tags") or [])]
    haystack = " ".join([prompt, cat, " ".join(item_tags), item.get("author", "")]).lower()

    matched: list[str] = []
    score = 0.0

    for tok in query_tokens:
        if tok in haystack:
            hits = haystack.count(tok)
            score += 3.0 + min(hits - 1, 3) * 0.4
            matched.append(tok)

    if category:
        if cat == category.lower():
            score += 4.0
        elif category.lower() in haystack:
            score += 1.0

    for tag in tags:
        wanted = normalize_tag(tag)
        if wanted in item_tags:
            score += 2.0
            matched.append(f"tag:{wanted}")
        elif wanted in haystack:
            score += 0.6

    if item.get("has_remake"):
        score += 1.5
    if item.get("prompt_partial"):
        score -= 1.0

    added = str(item.get("added") or "")
    if added >= "2026-09":
        score += 0.5

    if len(set(matched)) >= 2:
        score += 1.0

    return score, sorted(set(matched))


def short(text: str, n: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def download_poster(item: dict, outdir: Path, rank: int) -> str | None:
    url = item.get("poster_url")
    if not url:
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    ext = Path(url.split("?")[0]).suffix or ".webp"
    out = outdir / f"{rank:02d}-{item.get('slug', 'poster')}{ext}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dopamine-edit/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r, out.open("wb") as f:
            f.write(r.read())
        return str(out)
    except Exception as exc:  # noqa: BLE001 - posters are optional
        print(f"WARN: poster failed for {item.get('slug')}: {exc}", file=sys.stderr)
        return None


def print_prompt(refs: Path, slug: str) -> int:
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', slug):
        print('ERROR: invalid template slug', file=sys.stderr)
        return 2
    path = refs / "prompts" / f"{slug}.md"
    if path.exists():
        print(path.read_text())
        return 0
    items = load_library(refs)
    for item in items:
        if item.get("slug") == slug:
            print(f"# {slug}\n\n{item.get('prompt', '')}\n")
            print(f"Reference: {item.get('skillry_url', '')}")
            return 0
    print(f"ERROR: slug not found: {slug}", file=sys.stderr)
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refs-dir", default=str(DEFAULT_REFS))
    ap.add_argument("--query", default="")
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--category", choices=["motion", "3d", "explainer", "interactive"])
    ap.add_argument("--allow-cross-category", action="store_true",
                    help="let strong keyword matches override --category")
    ap.add_argument("--tags", default="", help="comma-separated tech tags")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", help="write a markdown shortlist to this path")
    ap.add_argument("--download-posters", help="directory for poster moodboard")
    ap.add_argument("--prompt", help="print the full prompt for a slug and exit")
    ap.add_argument("--list-presets", action="store_true")
    args = ap.parse_args()

    refs = Path(args.refs_dir).expanduser().resolve()

    if args.list_presets:
        print(json.dumps(PRESETS, indent=2))
        return 0
    if args.prompt:
        return print_prompt(refs, args.prompt)

    query = args.query
    category = args.category
    tags = [normalize_tag(t) for t in args.tags.split(",") if t.strip()]

    if args.preset:
        p = PRESETS[args.preset]
        query = query or p["query"]
        category = category or p["category"]
        tags = tags or list(p["tags"])

    if not query:
        print("ERROR: provide --query or --preset", file=sys.stderr)
        return 2

    items = load_library(refs)
    tokens = tokenize(query)
    ranked = []
    for item in items:
        if category and not args.allow_cross_category:
            if (item.get("category") or "").lower() != category.lower():
                continue
        s, matched = score_item(item, tokens, category, tags)
        if s >= args.min_score:
            ranked.append((s, matched, item))
    ranked.sort(key=lambda x: (-x[0], not x[2].get("has_remake"), x[2].get("slug", "")))

    top = ranked[: max(1, args.limit)]
    results = []
    for i, (s, matched, item) in enumerate(top, start=1):
        result = {
            "rank": i,
            "score": round(s, 2),
            "slug": item.get("slug"),
            "category": item.get("category"),
            "tech_tags": item.get("tech_tags", []),
            "has_remake": item.get("has_remake"),
            "author": item.get("author"),
            "prompt_excerpt": short(item.get("prompt", "")),
            "prompt_file": str(refs / "prompts" / f"{item.get('slug')}.md"),
            "skillry_url": item.get("skillry_url"),
            "poster_url": item.get("poster_url"),
            "matched_terms": matched,
            "why": ", ".join(matched[:8]),
        }
        if args.download_posters:
            result["poster_file"] = download_poster(item, Path(args.download_posters), i)
        results.append(result)

    payload = {
        "query": query,
        "category": category,
        "tags": tags,
        "tokens": tokens,
        "library": str(refs),
        "library_count": len(items),
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"query: {query}")
        print(f"library: {len(items)} prompts")
        for r in results:
            print(f"\n{r['rank']:>2}. {r['slug']}  [{r['category']}]  score {r['score']}")
            print(f"    tags: {', '.join(r['tech_tags']) or '—'} | remake: {r['has_remake']}")
            print(f"    {r['prompt_excerpt']}")
            print(f"    {r['skillry_url']}")
        print("\nread a full prompt with --prompt <slug>")

    if args.write:
        out = Path(args.write).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Template shortlist — {query}",
            "",
            f"Category: {category or 'any'} · Tags: {', '.join(tags) or 'any'} · "
            f"Library: {len(items)} prompts",
            "",
        ]
        for r in results:
            lines += [
                f"## {r['rank']}. `{r['slug']}` — score {r['score']}",
                "",
                f"- Category: {r['category']}",
                f"- Tags: {', '.join(r['tech_tags']) or '—'}",
                f"- Remake: {r['has_remake']}",
                f"- Reference: {r['skillry_url']}",
                f"- Prompt file: `{r['prompt_file']}`",
                f"- Why: {r['why']}",
                "",
                "> " + r["prompt_excerpt"],
                "",
            ]
        out.write_text("\n".join(lines))
        print(f"\nwrote {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
