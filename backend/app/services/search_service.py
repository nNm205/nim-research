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
        """Run the full search pipeline.

        ``filter_trusted`` (default True) drops any hit whose publisher is
        not in the trusted whitelist (arXiv / IEEE / ACM / ResearchGate).
        Set to False only for debugging — production callers always want
        the filter on so analyses don't pull from low-quality sources.
        """
        # Get tools  
        if not sources:
            tools = self.factory.get_default_tools()
        else:
            tools = self.factory.get_tools(sources)

        # Parallel search 
        # Pull more candidates than the user asked for: the trusted-
        # publisher filter drops a meaningful fraction (Google Scholar
        # in particular surfaces a lot of non-IEEE / non-ACM venues),
        # and we still want ``max_results`` after filtering.
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
        
        # Aggregate 
        documents = self.aggregator.aggregate(results)

        # Deduplicate
        documents = self.deduplicator.deduplicate(documents)

        # Trusted-publisher filter: tag every document with its
        # publisher (arXiv / IEEE / ACM / ResearchGate / other) and drop
        # the "other" bucket. We keep the publisher in raw_metadata so
        # downstream code (ingestion, FE display) can show a chip.
        if filter_trusted:
            documents = self._tag_and_filter(documents)
        
        # Rerank 
        documents = await self.reranker.rerank(query=query, documents=documents)
        
        return documents[:max_results]

    # ── Trusted-publisher filter ─────────────────────────────────────

    def _tag_and_filter(
        self, documents: list[SearchDocument]
    ) -> list[SearchDocument]:
        """Annotate each doc with its publisher and drop non-trusted ones.

        We keep the trusted whitelist enforcement here — at the search
        layer — instead of pushing it deeper into the ingestion service
        because the FE displays search results BEFORE the user picks
        any to ingest. Filtering here means the user never sees results
        they wouldn't be allowed to add to their project.
        """
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
            # Stash the publisher tag so the rest of the pipeline can
            # render a chip / pick the right PDF resolver.
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

