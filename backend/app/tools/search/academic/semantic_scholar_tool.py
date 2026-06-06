"""SemanticScholarTool — wraps the Semantic Scholar Graph API.

Rate-limit policy (per Semantic Scholar's docs):

    1 request per second, cumulative across all endpoints. This means that
    in a given second you may send only 1 request to our system and expect
    a successful response.

We enforce this with a module-level async lock + monotonic timestamp so the
tool can be safely called from multiple parallel pipelines (e.g. the
research agent kicks off arXiv + Scholar + Semantic Scholar in parallel
via ``asyncio.gather`` — without this lock the Semantic Scholar request
would race with itself if two agents start within the same second).

When the API still returns 429 — which happens occasionally during traffic
bursts even with the lock in place — we honour the ``Retry-After`` header
and otherwise back off exponentially.

The API key is read from ``settings.SEMANTIC_API_KEY`` and sent in the
``x-api-key`` header. With a key the rate is 1 RPS; without one it's much
lower (≈ 100 / 5 minutes / IP), so the key is strongly recommended.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from app.config import settings
from app.tools.search.base import BaseSearchTool
from app.tools.search.schemas.search_result import SearchDocument
from app.utils.constants import SearchSource, SearchType
from app.utils.logger import logger


# ── Rate limiter (module-level, shared across all instances) ─────────────────

# Keep a tiny safety margin above 1 s to account for clock skew and minor
# jitter between client and server timing.
_MIN_INTERVAL_S = 1.05
_rate_lock = asyncio.Lock()
_last_request_at: float = 0.0  # monotonic clock seconds


async def _wait_for_rate_slot() -> None:
    """Block until at least ``_MIN_INTERVAL_S`` has passed since the last
    Semantic Scholar request (cumulative across all endpoints).

    Must be called inside ``_rate_lock``.
    """
    global _last_request_at
    now = time.monotonic()
    elapsed = now - _last_request_at
    if elapsed < _MIN_INTERVAL_S:
        await asyncio.sleep(_MIN_INTERVAL_S - elapsed)
    _last_request_at = time.monotonic()


# ── Tool ─────────────────────────────────────────────────────────────────────

class SemanticScholarTool(BaseSearchTool):
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    FIELDS = ",".join([
        "title",
        "abstract",
        "authors",
        "year",
        "citationCount",
        "url",
        "externalIds",
        "fieldsOfStudy",
        "openAccessPdf",
    ])

    # Retry config — 4 attempts spaced by exponential backoff, capped at 8 s.
    _MAX_ATTEMPTS = 4
    _BACKOFF_BASE_S = 1.5
    _BACKOFF_CAP_S = 8.0

    async def search(
        self,
        query: str,
        max_results: int = 10,
        fields: Optional[str] = None,
        year: Optional[str] = None,
        fields_of_study: Optional[str] = None,
        min_citation_count: Optional[int] = None,
        open_access_pdf: bool = False,
    ) -> list[SearchDocument]:
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": fields or self.FIELDS,
        }
        if year:
            params["year"] = year
        if fields_of_study:
            params["fieldsOfStudy"] = fields_of_study
        if min_citation_count:
            params["minCitationCount"] = min_citation_count
        if open_access_pdf:
            params["openAccessPdf"] = ""

        headers = {"User-Agent": "nim-research/1.0"}
        api_key = (settings.SEMANTIC_API_KEY or "").strip()
        if api_key:
            headers["x-api-key"] = api_key
        else:
            logger.warning(
                "SemanticScholar: no SEMANTIC_API_KEY configured, requests "
                "will use the much stricter anonymous quota"
            )

        data = await self._request_with_retries(params=params, headers=headers)
        if data is None:
            return []

        return self._parse_response(data)

    # ── HTTP layer ──────────────────────────────────────────────────────────

    async def _request_with_retries(
        self,
        *,
        params: dict,
        headers: dict,
    ) -> dict | None:
        """Single API call gated by the global 1 RPS lock + retries on 429.

        Returns the decoded JSON body, or ``None`` if the call failed
        permanently (we deliberately swallow exceptions so a failed
        Semantic Scholar lookup doesn't take down the whole research
        session — the other search tools still produce results).
        """
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(self._MAX_ATTEMPTS):
                # Hold the global lock across the wait + the request itself
                # so two coroutines can never fire two requests inside the
                # same 1-second window.
                async with _rate_lock:
                    await _wait_for_rate_slot()
                    try:
                        response = await client.get(
                            self.BASE_URL, params=params, headers=headers
                        )
                    except httpx.RequestError as e:
                        logger.warning(
                            f"SemanticScholar: HTTP error on attempt "
                            f"{attempt + 1}: {e}"
                        )
                        # Fall through to the backoff path below.
                        response = None

                if response is not None and response.status_code == 200:
                    try:
                        return response.json()
                    except Exception as e:
                        logger.warning(
                            f"SemanticScholar: bad JSON in 200 response: {e}"
                        )
                        return None

                # 429 → honour Retry-After if present, else exponential backoff
                if response is not None and response.status_code == 429:
                    retry_after = self._parse_retry_after(response)
                    backoff = retry_after if retry_after is not None else (
                        min(
                            self._BACKOFF_BASE_S * (2 ** attempt),
                            self._BACKOFF_CAP_S,
                        )
                    )
                    logger.info(
                        f"SemanticScholar: rate limited (429). Backing off "
                        f"{backoff:.1f}s before attempt {attempt + 2}"
                    )
                    await asyncio.sleep(backoff)
                    continue

                # Any other non-200 — log and bail; retry won't help
                # (e.g. 4xx for a malformed query).
                if response is not None:
                    logger.warning(
                        f"SemanticScholar: non-retryable status "
                        f"{response.status_code} body={response.text[:200]!r}"
                    )
                    return None

                # response is None (network error) — exponential backoff
                backoff = min(
                    self._BACKOFF_BASE_S * (2 ** attempt),
                    self._BACKOFF_CAP_S,
                )
                await asyncio.sleep(backoff)

        logger.warning(
            f"SemanticScholar: giving up after {self._MAX_ATTEMPTS} attempts"
        )
        return None

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float | None:
        """Parse the ``Retry-After`` header as seconds. Per RFC 7231 it can
        be either an integer number of seconds or an HTTP-date; we only
        support the integer-seconds form because it's what S2 sends."""
        raw = response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    # ── Response parsing ────────────────────────────────────────────────────

    def _parse_response(self, data: dict) -> list[SearchDocument]:
        documents: list[SearchDocument] = []
        for paper in data.get("data", []):
            authors = [
                a.get("name")
                for a in paper.get("authors", [])
                if a.get("name")
            ]
            external_ids = paper.get("externalIds") or {}
            pdf_data = paper.get("openAccessPdf") or {}
            pdf_url = pdf_data.get("url") if pdf_data else None

            documents.append(
                SearchDocument(
                    title=paper.get("title") or "",
                    url=paper.get("url") or "",
                    snippet=paper.get("abstract"),
                    content_preview=paper.get("abstract"),
                    authors=authors,
                    published_at=None,
                    doi=external_ids.get("DOI"),
                    pdf_url=pdf_url,
                    source=SearchSource.SEMANTIC_SCHOLAR,
                    search_type=SearchType.ACADEMIC,
                    source_id=paper.get("paperId"),
                    retrieval_score=float(paper.get("citationCount") or 0),
                    raw_metadata={
                        "citation_count": paper.get("citationCount"),
                        "fields_of_study": paper.get("fieldsOfStudy"),
                        "year": paper.get("year"),
                    },
                )
            )
        return documents
