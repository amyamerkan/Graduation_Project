from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .normalization import expand_domain_terms


@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str = "intfloat/multilingual-e5-base"
    device: str = "cpu"
    batch_size: int = 32
    query_prefix: str = "query: "
    passage_prefix: str = "passage: "
    expand_terms: bool = True


class TransformerEncoder:
    """E5-style multilingual encoder with normalized vectors for cosine search."""

    def __init__(self, config: EmbeddingConfig):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Thiếu sentence-transformers. Chạy pip install -r requirements.txt") from exc
        self.config = config
        self.model = SentenceTransformer(config.model_name, device=config.device)

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def encode_passages(self, texts: Sequence[str]) -> np.ndarray:
        prepared = [self.config.passage_prefix + (expand_domain_terms(text) if self.config.expand_terms else text) for text in texts]
        return self._encode(prepared)

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        prepared = [self.config.query_prefix + (expand_domain_terms(text) if self.config.expand_terms else text) for text in texts]
        return self._encode(prepared)

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self.model.encode(
            list(texts), batch_size=self.config.batch_size, convert_to_numpy=True,
            normalize_embeddings=True, show_progress_bar=False,
        )
        return np.asarray(vectors, dtype="float32")


class HashingEncoder:
    """Offline smoke-test backend. Production builds must use TransformerEncoder."""

    def __init__(self, dimension: int = 1024):
        from sklearn.feature_extraction.text import HashingVectorizer

        self.vectorizer = HashingVectorizer(n_features=dimension, alternate_sign=False, ngram_range=(1, 2), norm="l2")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        return self.vectorizer.transform([expand_domain_terms(text) for text in texts]).toarray().astype("float32")

    encode_passages = _encode
    encode_queries = _encode


def create_encoder(config: EmbeddingConfig, backend: str = "transformer"):
    if backend == "transformer":
        return TransformerEncoder(config)
    if backend == "hashing":
        return HashingEncoder()
    raise ValueError(f"Backend embedding không hợp lệ: {backend}")
