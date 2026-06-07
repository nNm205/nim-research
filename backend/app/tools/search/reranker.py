import asyncio
from sentence_transformers import SentenceTransformer, util
from app.tools.search.schemas.search_result import SearchDocument


class SearchReranker:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    async def rerank(
        self,
        query: str,
        documents: list[SearchDocument],
        top_k: int | None = None
    ) -> list[SearchDocument]:
        if not documents:
            return []

        document_texts = [self._build_document_text(doc) for doc in documents]

        query_embedding, document_embeddings = await asyncio.gather(
            asyncio.to_thread(self.model.encode, query, convert_to_tensor=True),
            asyncio.to_thread(self.model.encode, document_texts, convert_to_tensor=True),
        )

        similarities = util.cos_sim(query_embedding, document_embeddings)[0]

        for doc, score in zip(documents, similarities):
            doc.relevance_score = float(score)

        documents.sort(key=lambda d: d.relevance_score or 0, reverse=True)

        if top_k:
            documents = documents[:top_k]

        return documents

    @staticmethod
    def _build_document_text(document: SearchDocument) -> str:
        parts = [
            document.title or "",
            document.snippet or "",
            document.content_preview or "",
        ]
        return "\n".join(filter(None, parts))
