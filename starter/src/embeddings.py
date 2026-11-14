"""Local embedding provider (Sentence Transformers) implementing the Embedder contract."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Real model only; any load or inference failure raises RuntimeError (no mock vectors)."""

    def __init__(self, model_name: str = "BAAI/bge-m3", batch_size: int = 16) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
            get_dim = getattr(self._model, "get_embedding_dimension", None) \
                or self._model.get_sentence_embedding_dimension
            self.dimensions = int(get_dim())
        except Exception as exc:
            raise RuntimeError(f"cannot load embedding model {model_name!r}: {exc}") from exc

    def _encode(self, texts: list[str]) -> list[list[float]]:
        try:
            vecs = self._model.encode(texts, batch_size=self.batch_size,
                                      normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:
            raise RuntimeError(f"embedding failed with {self.model_name!r}: {exc}") from exc
        return [[float(x) for x in v] for v in vecs]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts) if texts else []

    def embed_query(self, question: str) -> list[float]:
        return self._encode([question])[0]
