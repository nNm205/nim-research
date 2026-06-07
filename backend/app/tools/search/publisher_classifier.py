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
    OTHER = "other"   

_DOI_PREFIX_MAP: dict[str, Publisher] = {
    "10.48550": Publisher.ARXIV,
    "10.1109":  Publisher.IEEE,
    "10.1145":  Publisher.ACM,
}

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
    if source and source.lower() == "arxiv":
        return Publisher.ARXIV

    if doi:
        d = doi.strip().lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
            if d.startswith(prefix):
                d = d[len(prefix):]
                break
        head = d.split("/", 1)[0]
        match = _DOI_PREFIX_MAP.get(head)
        if match is not None:
            return match

    for candidate in (url, pdf_url):
        host = _host_of(candidate)
        if host:
            for suffix, pub in _HOST_SUFFIX_MAP:
                if host == suffix or host.endswith("." + suffix):
                    return pub

    return Publisher.OTHER


def is_trusted(publisher: Publisher) -> bool:
    return publisher in TRUSTED_PUBLISHERS

TRUSTED_PUBLISHERS: frozenset[Publisher] = frozenset({
    Publisher.ARXIV,
    Publisher.IEEE,
    Publisher.ACM,
    Publisher.RESEARCHGATE,
})

def _host_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None
    host = (parsed.netloc or "").lower()
   
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None
