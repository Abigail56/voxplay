"""Speaker embeddings with the pretrained SpeechBrain ECAPA-TDNN model.

The model (speechbrain/spkrec-ecapa-voxceleb) was trained on thousands of
VoxCeleb speakers. We never train it; we only use it to turn a clip into a
192-dimensional voiceprint. It is downloaded from Hugging Face on first start
(about 80 MB) and cached in MODEL_DIR.
"""

from __future__ import annotations

import threading
import warnings
from typing import Protocol

import numpy as np

from .matching import l2_normalize

EMBEDDING_DIM = 192


class Embedder(Protocol):
    """Anything that turns 16 kHz mono samples into a unit-length vector.

    The tests use a tiny fake embedder that follows this protocol, so they run
    in milliseconds without PyTorch.
    """

    def embed(self, samples: np.ndarray) -> np.ndarray: ...


class EcapaEmbedder:
    def __init__(self, source: str, savedir: str, num_threads: int = 2) -> None:
        # Imported here so that importing this module (e.g. in tests) does not
        # pull in PyTorch.
        import torch
        from speechbrain.inference.speaker import EncoderClassifier

        # SpeechBrain 1.0 triggers harmless deprecation warnings in newer PyTorch.
        warnings.filterwarnings("ignore", category=FutureWarning, module="speechbrain")
        torch.set_num_threads(num_threads)
        self._torch = torch
        self._model = EncoderClassifier.from_hparams(
            source=source, savedir=savedir, run_opts={"device": "cpu"}
        )
        self._model.eval()
        # One inference at a time: keeps memory predictable on small machines.
        self._lock = threading.Lock()

    def embed(self, samples: np.ndarray) -> np.ndarray:
        wav = self._torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32)).unsqueeze(0)
        with self._lock, self._torch.inference_mode():
            emb = self._model.encode_batch(wav)  # shape (1, 1, 192)
        return l2_normalize(emb.squeeze().cpu().numpy())

    def embed_many(self, clips: list[np.ndarray], batch_size: int = 16) -> list[np.ndarray]:
        """Embed many short clips at once (much faster than one by one on a CPU).

        Clips in a batch are zero-padded to the longest one; `wav_lens` tells the
        model how much of each row is real audio, so the padding is ignored.
        """
        out: list[np.ndarray] = []
        for i in range(0, len(clips), batch_size):
            batch = clips[i : i + batch_size]
            longest = max(c.size for c in batch)
            wavs = np.zeros((len(batch), longest), dtype=np.float32)
            for row, clip in enumerate(batch):
                wavs[row, : clip.size] = clip
            lens = self._torch.tensor([c.size / longest for c in batch], dtype=self._torch.float32)
            with self._lock, self._torch.inference_mode():
                emb = self._model.encode_batch(self._torch.from_numpy(wavs), lens)  # (batch, 1, 192)
            out.extend(l2_normalize(e) for e in emb.squeeze(1).cpu().numpy())
        return out


def embed_all(embedder: Embedder, clips: list[np.ndarray]) -> list[np.ndarray]:
    """Use the embedder's batched path when it has one (the fake test embedder doesn't)."""
    many = getattr(embedder, "embed_many", None)
    return many(clips) if many else [embedder.embed(c) for c in clips]
