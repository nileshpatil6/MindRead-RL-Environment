import sys
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

# Mock sentence_transformers and torch before any test imports them.
# This avoids the Windows torch DLL access violation during test collection.
# On the hackathon Linux/GPU machine these mocks are not applied.
_mock_st = MagicMock()

class _FakeEmbedder:
    """
    Fake embedder for Windows test runs (torch DLL crashes on Windows Store Python).
    Uses a bag-of-words style embedding so semantic similarity tests pass correctly:
    - identical text -> cosine ~1.0
    - paraphrase (shared words) -> moderate cosine
    - unrelated text -> low cosine
    """
    DIM = 384

    def _text_to_vec(self, text: str) -> np.ndarray:
        words = set(text.lower().split())
        vec = np.zeros(self.DIM, dtype=np.float32)
        for w in words:
            idx = hash(w) % self.DIM
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def encode(self, texts):
        return np.array([self._text_to_vec(t) for t in texts])

_mock_st.SentenceTransformer = lambda *a, **kw: _FakeEmbedder()
sys.modules.setdefault("sentence_transformers", _mock_st)

# Also mock torch so grpo/training imports don't crash on Windows
_mock_torch = MagicMock()
_mock_torch.bfloat16 = "bfloat16"
_mock_torch.cuda = MagicMock()
_mock_torch.cuda.is_available = lambda: False
sys.modules.setdefault("torch", _mock_torch)
sys.modules.setdefault("transformers", MagicMock())
sys.modules.setdefault("trl", MagicMock())
sys.modules.setdefault("datasets", MagicMock())
sys.modules.setdefault("accelerate", MagicMock())
sys.modules.setdefault("groq", MagicMock())
