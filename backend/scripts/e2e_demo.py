"""End-to-end demo against the running API, using real voices.

1. Enrolls the first --speakers speakers from /data/samples (2 clips each).
2. Identifies their held-out clips, converted to wav, mp3 AND webm/opus
   (the format browsers record in) - each should return the right name.
3. Identifies clips from a speaker who was never enrolled - should be "unknown".

    docker compose run --rm api python scripts/e2e_demo.py --api http://api:8000
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import httpx

FORMATS = {
    "wav": ["-f", "wav"],
    "mp3": ["-f", "mp3", "-b:a", "64k"],
    "webm": ["-f", "webm", "-c:a", "libopus", "-b:a", "32k"],
}
MIME = {"wav": "audio/wav", "mp3": "audio/mpeg", "webm": "audio/webm"}


def convert(path: Path, fmt: str) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), *FORMATS[fmt], "pipe:1"],
        capture_output=True, check=True,
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://api:8000")
    parser.add_argument("--data", default="/data/samples")
    parser.add_argument("--speakers", type=int, default=3)
    parser.add_argument("--tests-per-speaker", type=int, default=2)
    args = parser.parse_args()

    folders = sorted(p for p in Path(args.data).iterdir() if p.is_dir())
    enrolled, stranger = folders[: args.speakers], folders[args.speakers]
    client = httpx.Client(base_url=args.api, timeout=120)

    # Start clean: remove speakers left from a previous demo run.
    demo_names = {f"Speaker {f.name}" for f in folders}
    for s in client.get("/speakers").json():
        if s["name"] in demo_names:
            client.delete(f"/speakers/{s['id']}")

    print("== Enrollment ==")
    for folder in enrolled:
        clips = sorted(folder.iterdir())[:2]
        files = [("files", (c.name, c.read_bytes(), "audio/flac")) for c in clips]
        r = client.post("/speakers", data={"name": f"Speaker {folder.name}", "consent": "true"}, files=files)
        r.raise_for_status()
        print(f"  enrolled {r.json()['name']!r} with {r.json()['sample_count']} samples")

    print("\n== Identification ==")
    passed = total = 0
    for folder in [*enrolled, stranger]:
        expected = "unknown" if folder is stranger else f"Speaker {folder.name}"
        for clip in sorted(folder.iterdir())[2 : 2 + args.tests_per_speaker]:
            for fmt in FORMATS:
                r = client.post("/identify", files={"file": (f"{clip.stem}.{fmt}", convert(clip, fmt), MIME[fmt])})
                if r.status_code == 422:  # e.g. too little speech - the API rejects it on purpose
                    print(f"  SKIP  {clip.name:<22} {fmt:<5} -> {r.json()['detail']}")
                    continue
                r.raise_for_status()
                body = r.json()
                ok = body["label"] == expected
                passed += ok
                total += 1
                print(
                    f"  {'PASS' if ok else 'FAIL'}  {clip.name:<22} {fmt:<5} -> {body['label']:<16}"
                    f" score {body['score']:.3f}  (expected {expected})"
                )

    print(f"\n{passed}/{total} correct (threshold {body['threshold']})")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
