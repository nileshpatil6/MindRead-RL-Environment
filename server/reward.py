from __future__ import annotations
import numpy as np
from sentence_transformers import SentenceTransformer


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

_embedder: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedder


def compute_semantic_similarity(hypothesis: str, true_secret: str) -> float:
    embedder = get_embedder()
    emb_h = embedder.encode([hypothesis])[0]
    emb_t = embedder.encode([true_secret])[0]
    raw = _cosine(emb_h, emb_t)
    # random sentence pairs score ~0.2, normalize to [0, 1]
    return max(0.0, (raw - 0.2) / 0.8)


def compute_reward(
    hypothesis: str,
    true_secret: str,
    n_questions_used: int,
    max_questions: int,
    category_predicted: str | None,
    category_true: str,
    hint_keywords: list[str],
) -> dict:
    semantic = compute_semantic_similarity(hypothesis, true_secret)

    # fewer questions = higher bonus (range: 0.6 – 1.0)
    efficiency = 1.0 - (n_questions_used / max_questions) * 0.4

    category_bonus = 0.1 if category_predicted == category_true else 0.0

    hypothesis_lower = hypothesis.lower()
    kw_hits = sum(1 for kw in hint_keywords if kw.lower() in hypothesis_lower)
    keyword_bonus = min(0.1, 0.033 * kw_hits)

    base = semantic * efficiency
    total = min(1.0, base + category_bonus + keyword_bonus)

    return {
        "reward": round(total, 4),
        "components": {
            "semantic": round(semantic, 4),
            "efficiency": round(efficiency, 4),
            "category_bonus": category_bonus,
            "keyword_bonus": round(keyword_bonus, 4),
        },
    }
