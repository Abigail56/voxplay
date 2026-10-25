"""Turn generated artwork into the site's optimised WebP files, at the right size and path.

Generate the images with the prompts in docs/ART_PROMPTS.md, name each file after its asset
(e.g. `voxplay-hero.png`, `team-versus.jpg`, `nova.png`, `avatar-01.png`), put them all in one
folder, then run:

    python scripts/prepare_art.py ~/Downloads/voxplay-art

Scenes keep their whole picture (the site frames them with CSS object-position, so a square image
works in a wide slot) and are only scaled down so their longer side fits the target size. Portraits
and avatars are cropped square from the upper centre. Everything is saved as WebP and written to
frontend/public/images/voxplay/... Rebuild the site afterwards: the new images replace the drawn
scenes by themselves. Needs Pillow (`pip install pillow`); it's a tool for you, not a site dependency.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps

PUBLIC = Path(__file__).resolve().parents[1] / "frontend" / "public" / "images" / "voxplay"

# asset name -> (folder, width, aspect ratio w/h, WebP quality)
SCENE = (1600, 16 / 9, 80)
TILE = (1200, 16 / 10, 78)
STATE = (1000, 4 / 3, 78)
ASSETS: dict[str, tuple[str, int, float, int]] = {
    "voxplay-hero": ("hero", 2000, 16 / 9, 80),
    "voxplay-hero-mobile": ("hero", 1080, 4 / 5, 80),
    "arena": ("brain-clash", *SCENE),
    "team-versus": ("brain-clash", *SCENE),
    "victory": ("brain-clash", *SCENE),
    "defeat": ("brain-clash", *SCENE),
    "beat-drop": ("brain-clash", *SCENE),
    "story-forge": ("story-forge", *SCENE),
    "whos-talking": ("whos-talking", *SCENE),
    **{m: ("game-modes", *TILE) for m in (
        "african-knowledge", "music-challenge", "culture-challenge", "word-association",
        "riddles", "quick-fire", "general-knowledge", "team-battle", "name-it-fast",
    )},
    **{c: ("categories", *TILE) for c in (
        "african_general", "nigerian_general", "african_music", "nigerian_entertainment", "african_history",
        "current_affairs", "african_football", "animals_nature", "african_food", "languages", "pidgin",
        "african_movies", "riddles", "word_challenges", "everyday", "funny", "hum_afrobeats", "hum_amapiano",
        "hum_classics", "story_lagos", "story_legends", "story_chaos",
    )},
    **{s: ("states", *STATE) for s in ("searching", "waiting", "empty-room", "creating-room", "no-games", "reconnecting", "coming-soon")},
    **{c: ("characters", 1024, 1.0, 82) for c in ("nova", "pulse", "zuri", "ayo")},
    **{f"avatar-{i:02d}": ("avatars", 256, 1.0, 80) for i in range(1, 13)},
}


def fit(img: Image.Image, width: int, ratio: float) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("RGB")
    if ratio == 1.0:  # portraits and avatars must be square for round frames
        side = min(img.size)
        return ImageOps.fit(img, (min(side, width), min(side, width)), Image.LANCZOS, centering=(0.5, 0.3))
    scale = min(1.0, width / max(img.size))  # never enlarged
    return img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS) if scale < 1 else img


def main(inbox: Path) -> None:
    done, unknown = [], []
    for src in sorted(inbox.iterdir()):
        if src.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
            continue
        spec = ASSETS.get(src.stem.lower())
        if spec is None:
            unknown.append(src.name)
            continue
        folder, width, ratio, quality = spec
        out = PUBLIC / folder / f"{src.stem.lower()}.webp"
        out.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as img:
            fitted = fit(img, width, ratio)
        fitted.save(out, "WEBP", quality=quality, method=6)
        done.append(f"{out.relative_to(PUBLIC.parents[1])}  {fitted.width}x{fitted.height}  {out.stat().st_size // 1024} KB")
    print("\n".join(done) or "No images matched an asset name.")
    if unknown:
        print("\nNot used (name them after an asset in docs/ART_PROMPTS.md):", ", ".join(unknown))


if __name__ == "__main__":
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
