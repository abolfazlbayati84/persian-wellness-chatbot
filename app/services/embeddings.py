"""Local, free, offline embedding service (no external API, no rate limits).

Uses intfloat/multilingual-e5-base. The e5 model family requires a
"query: " / "passage: " prefix depending on which side of retrieval you're
on -- this is not optional, it's how the model was trained, and skipping it
measurably hurts retrieval quality.
"""

from functools import lru_cache

_MODEL_NAME = "intfloat/multilingual-e5-base"


@lru_cache(maxsize=1)
def _get_model():
    # imported lazily so the (heavy) sentence-transformers/torch import only
    # happens the first time an embedding is actually needed.
    from sentence_transformers import SentenceTransformer
    print(f"[EMBEDDINGS] loading model {_MODEL_NAME} (first call only)...")
    return SentenceTransformer(_MODEL_NAME)


def embed_passage(text: str) -> list[float]:
    """Embed a knowledge-base chunk (ingestion side)."""
    model = _get_model()
    vec = model.encode(f"passage: {text}", normalize_embeddings=True)
    return vec.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a user's chat message (retrieval side)."""
    model = _get_model()
    vec = model.encode(f"query: {text}", normalize_embeddings=True)
    return vec.tolist()