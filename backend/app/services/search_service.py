import asyncio 
from typing import Optional
from app.tools.search.factory import SearchToolFactory
from app.tools.search.aggregator import SearchAggregator
from app.tools.search.deduplicator import SearchDeduplicator
from app.tools.search.publisher_classifier import (
    Publisher,
    classify_publisher,
    is_trusted,
)
from app.tools.search.reranker import SearchReranker
from app.tools.search.schemas.search_result import SearchDocument
from app.utils.constants import SearchSource
from app.utils.logger import logger

class SearchService:
    def __init__(self):
        self.factory = SearchToolFactory()
        self.aggregator = SearchAggregator()
        self.deduplicator = SearchDeduplicator()
        self.reranker = SearchReranker()

    async def search(
        self, 
        query: str,
        max_results: int = 10,
        sources: Optional[list[SearchSource]] = None,
        *,
        filter_trusted: bool = True,
    ) -> list[SearchDocument]: 
        if not sources:
            tools = self.factory.get_default_tools()
        else:
            tools = self.factory.get_tools(sources)

        per_tool_max = max_results * 3 if filter_trusted else max_results
        tasks = [
            tool.search(
                query=query, 
                max_results=per_tool_max,
            ) for tool in tools 
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )
        
        documents = self.aggregator.aggregate(results)
        documents = self.deduplicator.deduplicate(documents)

        if filter_trusted:
            documents = self._tag_and_filter(documents)
        
        documents = await self.reranker.rerank(query=query, documents=documents)
        
        return documents[:max_results]

    def _tag_and_filter(
        self, documents: list[SearchDocument]
    ) -> list[SearchDocument]:
        kept: list[SearchDocument] = []
        dropped_other = 0
        for doc in documents:
            publisher = classify_publisher(
                doi=doc.doi,
                url=doc.url,
                pdf_url=doc.pdf_url,
                source=doc.source.value if doc.source else None,
            )
            if not is_trusted(publisher):
                dropped_other += 1
                continue
            
            meta = doc.raw_metadata or {}
            meta["publisher"] = publisher.value
            doc.raw_metadata = meta
            kept.append(doc)

        if dropped_other:
            logger.info(
                f"SearchService: filtered out {dropped_other} non-trusted "
                f"hit(s); kept {len(kept)} from {{arxiv, ieee, acm, "
                f"researchgate}}"
            )
        return kept

