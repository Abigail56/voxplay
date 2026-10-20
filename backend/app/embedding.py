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
