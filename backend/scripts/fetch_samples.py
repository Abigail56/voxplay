"""Download a few real voices to test with (a few MB).

Source: LibriSpeech dev-clean (people reading audiobooks, CC BY 4.0, recorded
for public research use), fetched clip-by-clip through the Hugging Face
dataset viewer API so we never download the full 340 MB file.

Output: /data/samples/<speaker_id>/<utterance>.flac

    docker compose run --rm api python scripts/fetch_samples.py
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROWS_URL = (
    "https://datasets-server.huggingface.co/rows?dataset=openslr/librispeech_asr"
    "&config=clean&split=validation&offset={offset}&length={length}"
)
TOTAL_ROWS = 2703  # size of dev-clean; rows are grouped by speaker


def get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/data/samples")
    parser.add_argument("--speakers", type=int, default=8)
    parser.add_argument("--clips", type=int, default=6, help="clips per speaker")
    args = parser.parse_args()

    out = Path(args.out)
    saved: dict[str, int] = {}
    # Jump through the dataset so each page lands on a different speaker.
    step = TOTAL_ROWS // (args.speakers + 1)
    for offset in range(0, TOTAL_ROWS, step):
        if len([s for s, n in saved.items() if n >= args.clips]) >= args.speakers:
            break
        rows = json.loads(get(ROWS_URL.format(offset=offset, length=args.clips * 2)))["rows"]
        for item in rows:
            row = item["row"]
            speaker = str(row["speaker_id"])
            if saved.get(speaker, 0) >= args.clips:
                continue
            folder = out / speaker
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{row['id']}.flac").write_bytes(get(row["audio"][0]["src"]))
            saved[speaker] = saved.get(speaker, 0) + 1

    for speaker, n in saved.items():
        print(f"  speaker {speaker}: {n} clips")
    print(f"Saved {len(saved)} speakers to {out}")


if __name__ == "__main__":
    main()
