"""Document I/O pipeline: fetch → parse → chunk → embed → store.

Subpackages:
    fetchers/      pull bytes from a URL (PDFFetcher, HTMLFetcher)
    parsers/       turn bytes into a structured ParsedDocument (PDFParser
                   via docling, HTMLParser, LegacyPDFParser fallback)
    chunkers/      split a ParsedDocument into chunks tagged with section
                   metadata (SectionAwareChunker)
    embeddings/    convert chunks into vectors via the EmbeddingProvider
                   abstraction (ProviderEmbeddingGenerator)
    vectorstores/  persist embedded chunks (PGVectorStore)
    schemas/       lightweight dataclasses passed between stages
"""
