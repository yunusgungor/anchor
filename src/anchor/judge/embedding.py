"""
Semantic Similarity — Embedding-based semantic distance for FactMatcher.

Phase 1 of the Judge pipeline: replaces Jaccard distance with cosine
similarity from a local sentence-transformer model.

Design principles:
  - OPTIONAL: system works without it (graceful None return)
  - LAZY: model only loaded on first use
  - DETERMINISTIC: same input → same embedding (no randomness)
  - LIGHTWEIGHT: all-MiniLM-L6-v2 falls within Anchor's memory budget
"""

import logging
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Global model cache (thread-safe)
_model_lock = threading.Lock()
_model = None
_model_name = None


def load_model(model_name: str = "paraphrase-multilingual-MiniLM-L12-v2") -> bool:
    """Load sentence-transformer model (lazy, cached).

    Args:
        model_name: HuggingFace model name or path.

    Returns:
        True if loaded successfully, False otherwise.
    """
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return True

    with _model_lock:
        # Double-check after acquiring lock
        if _model is not None and _model_name == model_name:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", model_name)
            _model = SentenceTransformer(model_name)
            _model_name = model_name
            logger.info("Embedding model loaded: %s (%d dim)",
                        model_name, _model.get_sentence_embedding_dimension())
            return True
        except ImportError:
            logger.warning("sentence-transformers not installed. "
                           "Install with: pip install anchor-engine[judge]")
            return False
        except Exception as e:
            logger.error("Failed to load embedding model %s: %s", model_name, e)
            return False


def is_available() -> bool:
    """Check if the embedding model is loaded and available."""
    return _model is not None


def encode(text: str, normalize: bool = True) -> Optional[np.ndarray]:
    """Encode a single text string to a vector.

    Args:
        text: Input text.
        normalize: L2-normalize the vector (for cosine similarity).

    Returns:
        numpy vector, or None if model not loaded.
    """
    if _model is None:
        return None
    try:
        vec = _model.encode(text, normalize_embeddings=normalize)
        return vec
    except Exception as e:
        logger.error("Encoding failed: %s", e)
        return None


def encode_batch(texts: list[str], normalize: bool = True) -> Optional[np.ndarray]:
    """Encode multiple texts in a batch.

    Args:
        texts: List of input texts.
        normalize: L2-normalize the vectors.

    Returns:
        2D numpy array (n_texts x dim), or None.
    """
    if _model is None:
        return None
    try:
        vecs = _model.encode(texts, normalize_embeddings=normalize)
        return vecs
    except Exception as e:
        logger.error("Batch encoding failed: %s", e)
        return None


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Cosine similarity between two vectors.

    Vectors are assumed to be L2-normalized (dot product = cosine).
    """
    return float(np.dot(vec_a, vec_b))


def semantic_distance(text_a: str, text_b: str) -> Optional[float]:
    """Compute semantic distance (1 - cosine_similarity) between two texts.

    Args:
        text_a: First text.
        text_b: Second text.

    Returns:
        Distance in [0, 2] range, or None if model unavailable.
        0 = identical, 1 = orthogonal, 2 = opposite.
    """
    if _model is None:
        return None
    try:
        vecs = _model.encode([text_a, text_b], normalize_embeddings=True)
        sim = float(np.dot(vecs[0], vecs[1]))
        # Clamp to [0, 1] for use as a distance metric
        sim = max(-1.0, min(1.0, sim))
        return 1.0 - sim
    except Exception as e:
        logger.error("Semantic distance failed: %s", e)
        return None
