"""Jina code embedding encoder for symbol vectorization."""

from __future__ import annotations

from typing import Literal

import torch
from transformers import AutoModel, AutoTokenizer

from praecepta.infra.codeintel.exceptions import EmbeddingError
from praecepta.infra.codeintel.settings import get_settings

TASK_PREFIXES: dict[str, str] = {
    "nl2code": "Retrieve the code that is relevant to the query\n",
    "code2code": "Retrieve the code that is semantically similar to the query code\n",
    "techqa": "Retrieve the document that answers the technical question\n",
}


class JinaEmbeddingEncoder:
    """Encode text into 1024-dimensional vectors using Jina code embeddings."""

    def __init__(self) -> None:
        settings = get_settings()
        try:
            self._model = AutoModel.from_pretrained(
                settings.embedding_model,
                trust_remote_code=True,
            )
            self._tokenizer = AutoTokenizer.from_pretrained(
                settings.embedding_model,
                trust_remote_code=True,
            )
            self._model.to(settings.embedding_device)
            self._model.eval()
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to load embedding model: {exc}",
                {"model": settings.embedding_model, "device": settings.embedding_device},
            ) from exc

        self._device = settings.embedding_device
        self._batch_size = settings.embedding_batch_size

    def encode(
        self,
        texts: list[str],
        query_type: Literal["nl2code", "code2code", "techqa"] = "nl2code",
    ) -> list[list[float]]:
        """Encode texts into embedding vectors."""
        prefix = TASK_PREFIXES.get(query_type, "")
        prefixed_texts = [prefix + t for t in texts]

        all_vectors: list[list[float]] = []

        for i in range(0, len(prefixed_texts), self._batch_size):
            batch = prefixed_texts[i : i + self._batch_size]
            try:
                encoded = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                ).to(self._device)

                with torch.no_grad():
                    outputs = self._model(**encoded)

                # Last-token pooling (autoregressive architecture)
                attention_mask = encoded["attention_mask"]
                last_token_indices = attention_mask.sum(dim=1) - 1
                embeddings = outputs.last_hidden_state[torch.arange(len(batch)), last_token_indices]

                # Normalize
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                all_vectors.extend(embeddings.cpu().tolist())

            except EmbeddingError:
                raise
            except Exception as exc:
                raise EmbeddingError(
                    f"Embedding inference failed: {exc}",
                    {"batch_size": len(batch)},
                ) from exc

        return all_vectors
