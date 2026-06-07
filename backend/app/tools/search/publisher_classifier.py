"""Publisher classifier — tag a SearchDocument with its trusted-publisher
identity based on DOI prefix and URL domain.

The user's "trusted publishers" whitelist is:
    - arXiv
    - IEEE
    - ACM
    - ResearchGate

We DO NOT add new search engines for IEEE / ACM / ResearchGate because:

  * IEEE Xplore: has an official API but requires a registered key and
    rate-limits aggressively; non-OA articles can't be downloaded
    legally anyway. Using Semantic Scholar / Google Scholar as the
    search engine + classifying by DOI prefix is the cleaner path.
  * ACM Digital Library: no public search API and the site explicitly
    prohibits scraping. Same Semantic-Scholar-then-classify approach.
  * ResearchGate: no API and ToS forbid automated access. We *can*
    surface RG-hosted papers when they show up in the index of a
    supported search engine, but we never download from RG itself —
    we resolve to an Open Access copy via DOI / Unpaywall instead.

So every paper passes through one of our existing search tools, and
this module just decides which trusted publisher (if any) it belongs
to. Anything that doesn't match a trusted publisher is dropped before
it can be ingested.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from urllib.parse import urlparse


class Publisher(str, Enum):
    """Trusted academic publisher / preprint-server label."""

    ARXIV = "arxiv"
    IEEE = "ieee"
    ACM = "acm"
    RESEARCHGATE = "researchgate"
    OTHER = "other"   # any non-trusted publisher; will be filtered out


# DOI prefix → publisher. DOIs are stable identifiers assigned per
# publisher, so the prefix is a near-perfect signal:
#   - 10.48550 / 10.48550 are arXiv's own DOIs (newer arXiv papers)
#   - 10.1109 is IEEE
#   - 10.1145 is ACM
# ResearchGate doesn't mint its own DOIs; an RG paper carries the DOI
# of the original venue, so we never match RG via DOI.
_DOI_PREFIX_MAP: dict[str, Publisher] = {
    "10.48550": Publisher.ARXIV,
    "10.1109":  Publisher.IEEE,
    "10.1145":  Publisher.ACM,
}


# URL host → publisher. Stripped of "www." / "scholar." / etc. before
# matching; subdomains like ``ieeexplore.ieee.org`` still match because
# we suffix-match on the registered domain.
#
# We deliberately keep this small — every other domain is treated as
# "other" (unknown / not trusted) and filtered out.
_HOST_SUFFIX_MAP: list[tuple[str, Publisher]] = [
    ("arxiv.org",         Publisher.ARXIV),
    ("ieee.org",          Publisher.IEEE),
    ("ieeexplore.ieee.org", Publisher.IEEE),
    ("computer.org",      Publisher.IEEE),     # IEEE Computer Society
    ("dl.acm.org",        Publisher.ACM),
    ("acm.org",           Publisher.ACM),
    ("researchgate.net",  Publisher.RESEARCHGATE),
]


def classify_publisher(
    *,
    doi: Optional[str] = None,
    url: Optional[str] = None,
    pdf_url: Optional[str] = None,
    source: Optional[str] = None,
) -> Publisher:
    """Tag a search hit with its trusted-publisher identity.

    Resolution order (most reliable first):
      1. ``source == 'arxiv'`` (already known from the ArxivTool) → arXiv.
      2. DOI prefix match — strongest signal because DOIs are publisher-
         scoped by registration.
      3. URL host match — covers landing-page links from Google Scholar
         results that don't carry a DOI (e.g. raw IEEE Xplore links).
      4. PDF URL host match — last resort, for results that only carry
         a direct PDF link.

    Returns ``Publisher.OTHER`` when nothing matches; the caller (the
    search aggregator + ingest service) treats that as "drop this hit".
    """
    # 1) Source label is the most authoritative when it's "arxiv" because
    #    that hit came directly from the arXiv API.
    if source and source.lower() == "arxiv":
        return Publisher.ARXIV

    # 2) DOI prefix.
    if doi:
        d = doi.strip().lower()
        # Strip the optional "doi:" / "https://doi.org/" wrapping.
        for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
            if d.startswith(prefix):
                d = d[len(prefix):]
                break
        head = d.split("/", 1)[0]
        match = _DOI_PREFIX_MAP.get(head)
        if match is not None:
            return match

    # 3) URL host.
    for candidate in (url, pdf_url):
        host = _host_of(candidate)
        if host:
            for suffix, pub in _HOST_SUFFIX_MAP:
                if host == suffix or host.endswith("." + suffix):
                    return pub

    return Publisher.OTHER


def is_trusted(publisher: Publisher) -> bool:
    """True iff ``publisher`` is in the user-configured trust whitelist."""
    return publisher in TRUSTED_PUBLISHERS


# Module-level whitelist — exported so the rest of the codebase
# (ingestion service, PDF finder, FE catalog endpoint) can refer to a
# single source of truth.
TRUSTED_PUBLISHERS: frozenset[Publisher] = frozenset({
    Publisher.ARXIV,
    Publisher.IEEE,
    Publisher.ACM,
    Publisher.RESEARCHGATE,
})


# ── Helpers ───────────────────────────────────────────────────────────

def _host_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None
    host = (parsed.netloc or "").lower()
    # Strip user info / port if present.
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None
