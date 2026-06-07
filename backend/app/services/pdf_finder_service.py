"""PDFFinderService — locate a downloadable PDF link for a search result.

Search results from arXiv / Semantic Scholar already include a ``pdf_url``
field most of the time, but Google Scholar and generic web search do not.
This service tries multiple strategies in order of decreasing reliability:

1. ``pdf_url`` already on the row → return it directly
   (UNLESS it points at researchgate.net — see policy note below).
2. arXiv abs URL (``arxiv.org/abs/...``) → derive ``arxiv.org/pdf/...``.
3. DOI present → query Unpaywall (free, no auth) for an open-access PDF.
4. Page URL ends in ``.pdf`` → trust the URL as-is
   (UNLESS it's on researchgate.net — see below).
5. Last resort: fetch the landing page HTML, look for a ``<meta>`` like
   ``citation_pdf_url`` or for an ``<a href>`` ending in ``.pdf``
   (UNLESS the landing page is on researchgate.net).

Returns ``None`` if no PDF could be located. Caller is expected to skip
the result in that case.

Compliance policy
─────────────────
We never download PDFs directly from ``researchgate.net``. RG's terms of
service forbid automated retrieval, and RG itself does not verify the
copyright of files uploaded by users. When a search hit's ONLY available
PDF link is on RG we resolve through Unpaywall instead (which only ever
returns confirmed Open Access copies). If no OA copy exists, we return
``None`` and let the caller skip the paper — better to lose one hit than
to ship code that violates a publisher's ToS.

For IEEE / ACM the situation is the same in principle: paywalled
articles can't be downloaded legally, so we lean on Unpaywall and the
publisher's own ``citation_pdf_url`` meta tag, which is only set on
freely-distributable copies.

The service is HTTP-only — it never writes to the DB.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

from app.utils.logger import logger


# Tunables
_HTTP_TIMEOUT = 15.0
_USER_AGENT = (
    "nim-eng-research/1.0 (+contact: research@example.com)"
)
_HTTP_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/json,text/html;q=0.9"}


# Unpaywall is a free index of open-access scholarly papers.
# Docs: https://unpaywall.org/products/api
_UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
_UNPAYWALL_EMAIL = "research@example.com"


# ── Heuristics on URLs ──────────────────────────────────────────────────────

# arXiv abs / pdf / html URL family.
#
# arXiv IDs come in two flavours:
#   - new-style:    YYMM.NNNNN          e.g. "1706.03762", "2310.12345"
#   - old-style:    archive[/.subj]/YYMMnnn   e.g. "cs/9605103", "cs.LG/9605103"
#
# After the id you may see:
#   - an optional version suffix     vN     e.g. "v5"
#   - an optional ".pdf"             when the URL is already a PDF link
#   - an optional trailing slash
#
# Match groups:
#   id      — the bare arXiv id (without version, without ".pdf").
#   version — captured but currently unused; kept for future use if we want
#             to fetch a specific version. Defaulting to no version means
#             we always grab the latest revision.
_NEW_STYLE_ID = r"\d{4}\.\d{4,5}"
_OLD_STYLE_ID = r"[a-z\-]+(?:\.[A-Z]{2})?/\d{7}"
_ARXIV_ID_RE = re.compile(
    r"https?://(?:www\.)?arxiv\.org/(?:abs|pdf|html)/"
    rf"(?P<id>{_OLD_STYLE_ID}|{_NEW_STYLE_ID})"
    r"(?P<version>v\d+)?"
    r"(?:\.pdf)?/?$",
    re.IGNORECASE,
)


def _derive_arxiv_pdf(url: str) -> str | None:
    """Map any arXiv URL to its canonical PDF URL.

    Accepts ``/abs/<id>``, ``/pdf/<id>(.pdf)``, ``/html/<id>``, with or
    without a version suffix, http or https, www or bare. Always returns
    the unversioned ``/pdf/<id>.pdf`` URL so the latest revision is used.

    Returns ``None`` if the URL doesn't look like an arXiv document URL.
    """
    if not url:
        return None
    m = _ARXIV_ID_RE.match(url.strip())
    if not m:
        return None
    return f"https://arxiv.org/pdf/{m.group('id')}.pdf"


def _looks_like_pdf_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(".pdf")


# Hosts we explicitly REFUSE to fetch from.
#
# ResearchGate's ToS forbids automated access AND the site does not
# verify copyright on user-uploaded files; we therefore never resolve
# a PDF URL that lives on RG. The URL is "valid" but ingesting it
# would be both legally and ethically dubious. Use Unpaywall to find
# a publisher-hosted OA copy instead.
_FORBIDDEN_PDF_HOSTS: frozenset[str] = frozenset({
    "researchgate.net",
})


def _is_forbidden_pdf_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    if ":" in host:
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return any(host == h or host.endswith("." + h) for h in _FORBIDDEN_PDF_HOSTS)


# ── Online lookups ──────────────────────────────────────────────────────────


async def _unpaywall_pdf(client: httpx.AsyncClient, doi: str) -> str | None:
    """Query Unpaywall for the best open-access PDF for ``doi``."""
    if not doi:
        return None
    try:
        resp = await client.get(
            f"{_UNPAYWALL_BASE}/{doi}",
            params={"email": _UNPAYWALL_EMAIL},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as e:
        logger.warning(f"PDFFinder: Unpaywall lookup failed for {doi}: {e}")
        return None

    # ``best_oa_location`` is the canonical OA copy. Fall back to first item
    # in ``oa_locations`` if the best one is missing for some reason.
    best = data.get("best_oa_location") or {}
    if best.get("url_for_pdf"):
        return best["url_for_pdf"]
    for loc in data.get("oa_locations") or []:
        if loc.get("url_for_pdf"):
            return loc["url_for_pdf"]
    return None


# ── HTML scraping helpers ───────────────────────────────────────────────────

# <meta name="citation_pdf_url" content="https://...pdf">  — common on academic
# pages (Google Scholar relies on it). This is the most reliable signal.
_META_PDF_RE = re.compile(
    r'<meta\s+[^>]*name=["\']citation_pdf_url["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
# Fallback: any <a href="...pdf"> that lives in the page.
_LINK_PDF_RE = re.compile(
    r'href=["\']([^"\']+\.pdf(?:[?#][^"\']*)?)["\']',
    re.IGNORECASE,
)


async def _scrape_pdf_from_landing(
    client: httpx.AsyncClient, url: str
) -> str | None:
    """Fetch the landing page HTML and look for a citation_pdf_url meta or
    a same-host ``<a href>`` ending in ``.pdf``."""
    try:
        resp = await client.get(url, follow_redirects=True)
    except Exception as e:
        logger.warning(f"PDFFinder: failed to fetch landing page {url}: {e}")
        return None

    if resp.status_code != 200 or "html" not in (resp.headers.get("content-type") or ""):
        return None

    html = resp.text[:200_000]  # cap — we only need the head + first chunk

    # citation_pdf_url meta is the strongest signal
    m = _META_PDF_RE.search(html)
    if m:
        return urljoin(str(resp.url), m.group(1))

    # Fallback: first <a href="...pdf"> on the page
    for href_match in _LINK_PDF_RE.finditer(html):
        candidate = urljoin(str(resp.url), href_match.group(1))
        # Skip obviously-irrelevant patterns (e.g. linked to some library)
        if "javascript:" in candidate.lower():
            continue
        return candidate

    return None


# ── Public API ──────────────────────────────────────────────────────────────


class PDFFinderService:
    """Locate a downloadable PDF for a SearchResult-like dict."""

    async def find(
        self,
        *,
        url: str | None,
        pdf_url: str | None = None,
        doi: str | None = None,
        source: str | None = None,
        source_id: str | None = None,
    ) -> str | None:
        # 1) Already have it — but reject ResearchGate-hosted PDFs per
        #    policy. The DOI lookup further down will recover an OA
        #    copy from the original publisher when one exists.
        if pdf_url and pdf_url.strip():
            if _is_forbidden_pdf_url(pdf_url):
                logger.info(
                    "PDFFinder: refusing to fetch ResearchGate-hosted PDF "
                    f"({pdf_url}); will try Unpaywall via DOI"
                )
            else:
                return pdf_url.strip()

        # 2) arXiv: try multiple paths.
        # 2a) ``source == arxiv`` + ``source_id`` is the most reliable case
        #     (the ArxivTool extracts ``source_id`` from the atom feed entry).
        if source == "arxiv" and source_id:
            normalised = source_id.strip().rstrip("/")
            # Strip any version suffix so we always get the latest version.
            normalised_no_v = re.sub(r"v\d+$", "", normalised)
            return f"https://arxiv.org/pdf/{normalised_no_v}.pdf"
        # 2b) URL pattern match (e.g. arxiv result mediated through Google
        #     Scholar still has ``url == arxiv.org/abs/...``).
        derived = _derive_arxiv_pdf(url) if url else None
        if derived:
            return derived

        # 3) URL itself is already a .pdf — trust it unless it's on a
        #    forbidden host.
        if url and _looks_like_pdf_url(url) and not _is_forbidden_pdf_url(url):
            return url

        # 4 + 5) Anything else needs HTTP.
        try:
            async with httpx.AsyncClient(
                timeout=_HTTP_TIMEOUT,
                headers=_HTTP_HEADERS,
                follow_redirects=True,
            ) as client:
                if doi:
                    via_unpaywall = await _unpaywall_pdf(client, doi.strip())
                    if via_unpaywall and not _is_forbidden_pdf_url(via_unpaywall):
                        return via_unpaywall

                # Skip landing-page scraping when the landing page itself
                # is on a forbidden host (RG). Even though the scraped
                # PDF link MIGHT point off-host, the safest behaviour is
                # to never make automated requests against the host at
                # all.
                if url and not _is_forbidden_pdf_url(url):
                    scraped = await _scrape_pdf_from_landing(client, url)
                    if scraped and not _is_forbidden_pdf_url(scraped):
                        return scraped
        except Exception as e:
            logger.warning(f"PDFFinder: HTTP lookup chain failed: {e}")

        return None
