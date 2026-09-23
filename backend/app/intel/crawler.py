"""Safe website fetcher + parser (Phase 1).

- URL validation (http/https only, no private hosts by default)
- httpx fetch with timeout + size cap
- stdlib HTML parsing: title, meta description, headings, links,
  emails, phones, social links, CTAs
- Multi-page crawl: home + common pages (about/services/pricing/...)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

FETCH_TIMEOUT = 15.0
MAX_BYTES = 2_000_000
COMMON_PATHS = [
    "/", "/about", "/about-us", "/services", "/products", "/pricing",
    "/contact", "/contact-us", "/faq", "/careers", "/case-studies",
    "/solutions", "/features",
]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
SOCIAL_DOMAINS = ("linkedin.com", "twitter.com", "x.com", "facebook.com",
                  "instagram.com", "youtube.com", "github.com")


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_desc = ""
        self.h: list[str] = []
        self.list_items: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self._in_head = False
        self._cur_link: str | None = None
        self._cur_link_text = ""
        self._cur_heading: str | None = None
        self._in_li = False
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        at = dict(attrs)
        if tag == "head":
            self._in_head = True
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style"}:
            self._skip = True
        if tag in {"h1", "h2", "h3"}:
            self._cur_heading = tag
        if tag == "li":
            self._in_li = True
        if tag == "meta" and at.get("name", "").lower() == "description":
            self.meta_desc = at.get("content", "")[:2000]
        if tag == "a" and at.get("href"):
            self._cur_link = at["href"]
            self._cur_link_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self._in_head = False
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style"}:
            self._skip = False
        if tag in {"h1", "h2", "h3"}:
            self._cur_heading = None
        if tag == "li":
            self._in_li = False
        if tag == "a" and self._cur_link is not None:
            self.links.append((self._cur_link, self._cur_link_text.strip()[:200]))
            self._cur_link = None

    def handle_data(self, data: str) -> None:
        s = data.strip()
        if not s:
            return
        if self._in_title:
            self.title += s
        if self._cur_link is not None and not self._skip:
            self._cur_link_text += " " + s
        if self._skip:
            return
        # skip head boilerplate except title/meta
        if self._in_head and not self._in_title:
            return
        if self._cur_heading and len(s) > 1:
            self.h.append(s[:200])
        if self._in_li and len(s) > 2 and self._cur_link is None:
            self.list_items.append(s[:200])
        if len(s) > 1:
            self.text_parts.append(s)


@dataclass
class PageData:
    url: str
    title: str = ""
    meta_description: str = ""
    text: str = ""
    links: list[dict] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_links: list[str] = field(default_factory=list)
    ctas: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    list_items: list[str] = field(default_factory=list)


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError(f"invalid URL: {url}")
    # block localhost/private to avoid SSRF in default config
    host = p.hostname.lower()
    if host in ("localhost", "127.0.0.1", "::1") or host.startswith("169.254."):
        raise ValueError("private/local URLs are not allowed")
    if host.startswith("10.") or host.startswith("192.168."):
        raise ValueError("private network URLs are not allowed")
    return url


def parse_html(url: str, html: str) -> PageData:
    parser = _TextParser()
    try:
        parser.feed(html[:MAX_BYTES])
    except Exception:
        pass
    text = " ".join(parser.text_parts)
    text = re.sub(r"\s+", " ", text)[:20000]
    abs_links = []
    social: list[str] = []
    ctas: list[str] = []
    for href, ltext in parser.links:
        try:
            full = urljoin(url, href)
        except Exception:
            continue
        abs_links.append({"href": full, "text": ltext})
        low = full.lower()
        if any(d in low for d in SOCIAL_DOMAINS):
            if full not in social:
                social.append(full)
        if ltext and any(
            k in ltext.lower()
            for k in ("contact", "get started", "book", "demo", "trial",
                      "sign up", "pricing", "call", "quote", "hire")
        ):
            if ltext not in ctas:
                ctas.append(ltext)
    emails = sorted(set(EMAIL_RE.findall(html)))[:20]
    phones = sorted(set(PHONE_RE.findall(text)))[:10]
    headings = [h for h in dict.fromkeys(parser.h) if h][:30]
    items = [li for li in dict.fromkeys(parser.list_items) if li][:40]
    return PageData(
        url=url, title=parser.title[:300], meta_description=parser.meta_desc,
        text=text, links=abs_links[:200], emails=emails,
        phones=phones, social_links=social[:20], ctas=ctas[:20],
        headings=headings, list_items=items,
    )


def fetch_page(url: str, client=None) -> tuple[str, PageData]:
    """Fetch one page. Returns (html, parsed). Raises on failure."""
    import httpx

    url = validate_url(url)
    close = False
    if client is None:
        client = httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True,
                              headers={"User-Agent": "MAICOS-Bot/1.0"})
        close = True
    try:
        r = client.get(url)
        r.raise_for_status()
        html = r.text[:MAX_BYTES]
        return html, parse_html(str(r.url), html)
    finally:
        if close:
            try:
                client.close()
            except Exception:
                pass


SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
                   ".pdf", ".zip", ".mp4", ".css", ".js", ".ico", ".woff2")


def _same_origin_link(href: str, host: str) -> str | None:
    """Keep crawl on the site itself; skip assets, anchors, externals."""
    try:
        full = urljoin(f"https://{host}/", href)
        p = urlparse(full)
    except Exception:
        return None
    if p.scheme not in ("http", "https") or (p.hostname or "").lower() != host:
        return None
    if p.fragment and not p.path:
        return None
    if p.path.lower().endswith(SKIP_EXTENSIONS):
        return None
    return f"{p.scheme}://{p.netloc}{p.path or '/'}".rstrip("/") or f"{p.scheme}://{p.netloc}/"


def crawl_site(base_url: str, max_pages: int = 10) -> list[PageData]:
    """Fetch home + common pages, then follow same-origin links (BFS).

    Never raises — returns what succeeded.
    """
    import httpx

    base = validate_url(base_url)
    parsed = urlparse(base)
    host = (parsed.hostname or "").lower()
    origin = f"{parsed.scheme}://{parsed.netloc}"
    queue = [base] + [origin + p for p in COMMON_PATHS[1:]]
    seen: set[str] = set()
    out: list[PageData] = []
    try:
        client = httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True,
                              headers={"User-Agent": "MAICOS-Bot/1.0"})
    except Exception:
        return out
    try:
        while queue and len(out) < max_pages:
            u = queue.pop(0)
            key = u.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            try:
                _, page = fetch_page(u, client)
            except Exception:
                continue
            if not (page.text.strip() or page.headings):
                continue
            out.append(page)
            # Discover more same-origin pages from this page's links.
            for link in page.links:
                if len(out) + len(queue) >= max_pages + 20:
                    break
                nxt = _same_origin_link(link["href"], host)
                if nxt and nxt.rstrip("/") not in seen:
                    queue.append(nxt)
    finally:
        try:
            client.close()
        except Exception:
            pass
    return out
