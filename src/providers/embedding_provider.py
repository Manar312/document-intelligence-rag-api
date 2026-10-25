from fastembed import TextEmbedding


class EmbeddingProvider:
    def __init__(self, model_name: str, dimensions: int) -> None:
        self.model = TextEmbedding(model_name=model_name)
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = [vector.tolist() for vector in self.model.embed(texts)]
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("Embedding dimensions do not match configuration.")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        if not vectors:
            raise ValueError("Query text cannot be empty.")
        return vectors[0]
