from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_providers.factory import EmbeddingFactory
from app.models.embedding_providers.types import EmbeddingProviderType
from app.tools.document.fetchers.pdf_fetcher import PDFFetcher
from app.tools.document.fetchers.html_fetcher import HTMLFetcher
from app.tools.document.parsers.pdf_parser import PDFParser
from app.tools.document.parsers.html_parser import HTMLParser
from app.tools.document.chunkers.section_aware_chunker import SectionAwareChunker
from app.tools.document.embeddings.provider_embedding import ProviderEmbeddingGenerator
from app.tools.document.vectorstores.factory import VectorStoreFactory
from app.utils.logger import logger

def _build_embedder(
    provider_override: str | None = None,
    model_override: str | None = None,
) -> ProviderEmbeddingGenerator:
    provider_type = EmbeddingProviderType(provider_override or settings.EMBEDDING_PROVIDER)
    model = model_override or settings.EMBEDDING_MODEL or None
    provider = EmbeddingFactory.create_provider(provider_type, model=model)
    return ProviderEmbeddingGenerator(provider)

class DocumentIngestionService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
    ):
        self.db = db
        self.pdf_fetcher = PDFFetcher()
        self.html_fetcher = HTMLFetcher()
        self.pdf_parser = PDFParser()
        self.html_parser = HTMLParser()
        self.chunker = SectionAwareChunker()
        self.embedder = _build_embedder(embedding_provider, embedding_model)
        self.vector_store = VectorStoreFactory.create(db)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _is_pdf_url(self, url: str) -> bool:
        """Detect PDF by URL extension or common PDF hosting patterns."""
        url_lower = url.lower().split("?")[0]  # strip query params
        if url_lower.endswith(".pdf"):
            return True
        # arXiv PDF links
        if "arxiv.org/pdf/" in url_lower:
            return True
        return False

    async def _persist_document_and_chunks(
        self,
        project_id: UUID,
        title: str,
        source_url: str,
        source_type: str,
        text: str,
        tables: list | None = None,
        formulas: list | None = None,
    ) -> Document:
        """Shared logic: create Document, chunk, embed, upsert vectors."""
        document_metadata: dict | None = None
        if tables or formulas:
            document_metadata = {}
            if tables:
                document_metadata["tables"] = [t.to_dict() for t in tables]
            if formulas:
                document_metadata["formulas"] = [f.to_dict() for f in formulas]

        document = Document(
            project_id=project_id,
            title=title,
            source_url=source_url,
            source_type=source_type,
            content=text,
            document_metadata=document_metadata,
            file_path=None,
            processed=False,
        )

        self.db.add(document)
        await self.db.flush()

        # Chunk
        tool_chunks = await self.chunker.chunk(text)

        # Create ORM chunk models with section metadata for downstream analysis
        chunk_models = []
        for tool_chunk in tool_chunks:
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=tool_chunk.chunk_id,
                content=tool_chunk.text,
                chunk_metadata=tool_chunk.metadata or None,
            )
            chunk_models.append(chunk)

        self.db.add_all(chunk_models)
        await self.db.flush()

        # Embed
        embedded_chunks = await self.embedder.embed_chunks(tool_chunks)

        # Upsert vectors
        chunk_ids = [chunk.id for chunk in chunk_models]
        vectors = [ec.embedding for ec in embedded_chunks]

        await self.vector_store.upsert_many(
            chunk_ids=chunk_ids,
            vectors=vectors,
            model_name=self.embedder._provider.get_model_name(),
        )

        document.processed = True
        await self.db.commit()
        await self.db.refresh(document)

        return document

    # ── Public methods ────────────────────────────────────────────────────────

    async def ingest_from_search_result(
        self,
        project_id: UUID,
        search_result,
    ) -> Document:
        """Best-effort ingest of a SearchResult row.

        Strategy:
          1. Locate a downloadable PDF (existing ``pdf_url``, derived arXiv
             link, Unpaywall via DOI, or scraped from the landing page).
          2. If we found one: ingest it via ``ingest_pdf``.
          3. Otherwise fall back to ``ingest_html`` on the landing URL — at
             least the user gets the page text + metadata in their project.

        Always returns a ``Document``. The caller can inspect
        ``document.source_type`` to know which path was taken (``pdf`` /
        ``web`` / ``academic`` / ``uploaded``).
        """
        from app.services.pdf_finder_service import PDFFinderService

        finder = PDFFinderService()
        pdf_url = await finder.find(
            url=getattr(search_result, "url", None),
            pdf_url=getattr(search_result, "pdf_url", None),
            doi=getattr(search_result, "doi", None),
            source=getattr(search_result, "source", None),
            source_id=getattr(search_result, "source_id", None),
        )

        if pdf_url:
            logger.info(
                f"DocumentIngestion: search result {getattr(search_result, 'id', '?')} "
                f"→ PDF at {pdf_url}"
            )
            try:
                doc = await self.ingest_pdf(project_id=project_id, pdf_url=pdf_url)
                # Override the title if the search result has a cleaner one
                # than what the PDF parser auto-detected.
                title = getattr(search_result, "title", None)
                if title and (not doc.title or doc.title.strip().lower() == "untitled"):
                    doc.title = title
                    await self.db.commit()
                    await self.db.refresh(doc)
                return doc
            except Exception as e:
                logger.warning(
                    f"DocumentIngestion: PDF ingest failed for {pdf_url} "
                    f"({e}); falling back to HTML"
                )

        # Fallback: ingest the landing page as HTML.
        landing_url = getattr(search_result, "url", None)
        if not landing_url:
            raise ValueError("Search result has no URL to ingest from")

        source = getattr(search_result, "source", None) or "web"
        # Map our internal SearchSource enum strings to source_type values
        # the rest of the app understands.
        source_type = "academic" if source in {
            "arxiv", "google_scholar", "semantic_scholar"
        } else "web"

        return await self.ingest_html(
            project_id=project_id,
            url=landing_url,
            source_type=source_type,
        )

    async def ingest_pdf(
        self,
        project_id: UUID,
        pdf_url: str,
    ) -> Document:
        fetched_doc = None
        try:
            fetched_doc = await self.pdf_fetcher.fetch(pdf_url)
            parsed_doc = await self.pdf_parser.parse(fetched_doc.local_path)

            try:
                fetched_doc.local_path.unlink(missing_ok=True)
            except Exception:
                pass

            return await self._persist_document_and_chunks(
                project_id=project_id,
                title=parsed_doc.title or pdf_url.split("/")[-1],
                source_url=pdf_url,
                source_type="pdf",
                text=parsed_doc.text,
                tables=parsed_doc.tables,
                formulas=parsed_doc.formulas,
            )

        except Exception as e:
            if fetched_doc is not None:
                try:
                    fetched_doc.local_path.unlink(missing_ok=True)
                except Exception:
                    pass
            await self.db.rollback()
            raise e

    async def ingest_uploaded_file(
        self,
        project_id: UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> Document:
        """Persist an uploaded file (PDF or HTML) and run the full pipeline.

        We accept the file in-memory (FastAPI ``UploadFile.read()``) and
        write it to a NamedTemporaryFile on disk so the existing parsers
        — which expect a ``Path`` argument — work unchanged. The temp
        file is removed once parsing completes.
        """
        import tempfile
        from pathlib import Path

        # Decide which parser to use. Prefer extension; fall back to mime type.
        lower = (filename or "").lower()
        is_pdf = lower.endswith(".pdf") or (content_type or "").lower().startswith(
            "application/pdf"
        )
        is_html = (
            lower.endswith(".html")
            or lower.endswith(".htm")
            or (content_type or "").lower().startswith("text/html")
        )

        if not is_pdf and not is_html:
            raise ValueError(
                "Định dạng không hỗ trợ. Chỉ chấp nhận PDF (.pdf) hoặc HTML (.html/.htm)."
            )

        suffix = ".pdf" if is_pdf else ".html"

        # Persist to a temp file because parsers operate on file paths.
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = Path(tmp.name)
        try:
            tmp.write(file_bytes)
            tmp.close()

            if is_pdf:
                parsed_doc = await self.pdf_parser.parse(tmp_path)
                source_type = "pdf"
            else:
                parsed_doc = await self.html_parser.parse(tmp_path)
                source_type = "uploaded"

            if not parsed_doc.text.strip():
                raise ValueError("Không tìm thấy nội dung đọc được trong file.")

            return await self._persist_document_and_chunks(
                project_id=project_id,
                title=parsed_doc.title or filename,
                # Uploaded files have no canonical URL; record the original
                # filename in source_url for traceability.
                source_url=f"upload://{filename}",
                source_type=source_type,
                text=parsed_doc.text,
                tables=parsed_doc.tables,
                formulas=parsed_doc.formulas,
            )

        except Exception:
            await self.db.rollback()
            raise
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    async def ingest_html(
        self,
        project_id: UUID,
        url: str,
        source_type: str = "web",
    ) -> Document:
        fetched_doc = None
        try:
            fetched_doc = await self.html_fetcher.fetch(url)
            parsed_doc = await self.html_parser.parse(fetched_doc.local_path)

            try:
                fetched_doc.local_path.unlink(missing_ok=True)
            except Exception:
                pass

            if not parsed_doc.text.strip():
                raise ValueError("No readable content found at this URL")

            return await self._persist_document_and_chunks(
                project_id=project_id,
                title=parsed_doc.title or url,
                source_url=url,
                source_type=source_type,
                text=parsed_doc.text,
                tables=parsed_doc.tables,
                formulas=parsed_doc.formulas,
            )

        except Exception as e:
            if fetched_doc is not None:
                try:
                    fetched_doc.local_path.unlink(missing_ok=True)
                except Exception:
                    pass
            await self.db.rollback()
            raise e

    async def ingest_url(
        self,
        project_id: UUID,
        url: str,
        source_type: str = "web",
    ) -> Document:
        """Auto-detect PDF vs HTML and ingest accordingly."""
        if self._is_pdf_url(url):
            return await self.ingest_pdf(project_id, url)
        else:
            return await self.ingest_html(project_id, url, source_type=source_type)
