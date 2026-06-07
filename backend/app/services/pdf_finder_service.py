from __future__ import annotations
import re
from urllib.parse import urljoin, urlparse
import httpx
from app.utils.logger import logger

_HTTP_TIMEOUT = 15.0
_USER_AGENT = (
    "nim-eng-research/1.0 (+contact: research@example.com)"
)
_HTTP_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/json,text/html;q=0.9"}
_UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
_UNPAYWALL_EMAIL = "research@example.com"

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

async def _unpaywall_pdf(client: httpx.AsyncClient, doi: str) -> str | None:
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

    best = data.get("best_oa_location") or {}
    if best.get("url_for_pdf"):
        return best["url_for_pdf"]
    for loc in data.get("oa_locations") or []:
        if loc.get("url_for_pdf"):
            return loc["url_for_pdf"]
    return None

_META_PDF_RE = re.compile(
    r'<meta\s+[^>]*name=["\']citation_pdf_url["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_LINK_PDF_RE = re.compile(
    r'href=["\']([^"\']+\.pdf(?:[?#][^"\']*)?)["\']',
    re.IGNORECASE,
)


async def _scrape_pdf_from_landing(
    client: httpx.AsyncClient, url: str
) -> str | None:
    try:
        resp = await client.get(url, follow_redirects=True)
    except Exception as e:
        logger.warning(f"PDFFinder: failed to fetch landing page {url}: {e}")
        return None

    if resp.status_code != 200 or "html" not in (resp.headers.get("content-type") or ""):
        return None

    html = resp.text[:200_000]  
    m = _META_PDF_RE.search(html)
    if m:
        return urljoin(str(resp.url), m.group(1))

    for href_match in _LINK_PDF_RE.finditer(html):
        candidate = urljoin(str(resp.url), href_match.group(1))
        if "javascript:" in candidate.lower():
            continue
        return candidate

    return None


class PDFFinderService:
    async def find(
        self,
        *,
        url: str | None,
        pdf_url: str | None = None,
        doi: str | None = None,
        source: str | None = None,
        source_id: str | None = None,
    ) -> str | None:
        if pdf_url and pdf_url.strip():
            if _is_forbidden_pdf_url(pdf_url):
                logger.info(
                    "PDFFinder: refusing to fetch ResearchGate-hosted PDF "
                    f"({pdf_url}); will try Unpaywall via DOI"
                )
            else:
                return pdf_url.strip()

        if source == "arxiv" and source_id:
            normalised = source_id.strip().rstrip("/")
            normalised_no_v = re.sub(r"v\d+$", "", normalised)
            return f"https://arxiv.org/pdf/{normalised_no_v}.pdf"
        
        derived = _derive_arxiv_pdf(url) if url else None
        if derived:
            return derived

        if url and _looks_like_pdf_url(url) and not _is_forbidden_pdf_url(url):
            return url

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

                if url and not _is_forbidden_pdf_url(url):
                    scraped = await _scrape_pdf_from_landing(client, url)
                    if scraped and not _is_forbidden_pdf_url(scraped):
                        return scraped
        except Exception as e:
            logger.warning(f"PDFFinder: HTTP lookup chain failed: {e}")

        return None
