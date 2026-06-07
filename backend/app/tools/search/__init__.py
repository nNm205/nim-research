"""Search adapters and pipeline glue.

Top-level modules:
    base.py                  abstract ``BaseSearchTool`` (one source per impl)
    factory.py               instantiates the right tool given a SearchSource
    aggregator.py            run multiple tools concurrently and merge
    deduplicator.py          drop duplicates by URL / DOI / fuzzy title
    reranker.py              cross-encoder semantic re-ranking
    publisher_classifier.py  arxiv / ieee / acm / researchgate / other

Subpackages:
    academic/                arXiv, Google Scholar (SerpAPI), Semantic Scholar
    web/                     SerpAPI generic web search
    schemas/                 dataclasses used across the pipeline
"""
