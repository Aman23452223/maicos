"""Intel depth: multi-page crawl, specific services, specific audience."""
from __future__ import annotations

HTML = (
    "<html><head><title>FixKaro - Home Services at Your Doorstep</title>"
    '<meta name="description" content="Book trusted local professionals '
    'for plumbing, electrical, AC repair in Nagpur."></head>'
    '<body><nav><a href="/services">Services</a><a href="/about">About</a>'
    '<a href="/book">Book Now</a></nav>'
    "<h1>Home Services at Your Doorstep</h1><h2>Plumbing Repair</h2>"
    "<h2>AC Service and Repair</h2>"
    "<ul><li>Tap and mixer repair</li><li>Split AC deep cleaning</li></ul>"
    "<p>Trusted by homeowners across Nagpur. Call 9876543210.</p>"
    "</body></html>"
)


def test_services_specific_not_title_echo():
    from app.intel.crawler import parse_html
    from app.intel.profiles import extract_profile

    p = parse_html("https://fixkaro.test/", HTML)
    prof = extract_profile([p], "https://fixkaro.test/")
    assert "Plumbing Repair" in prof["services"]
    assert "FixKaro - Home Services at Your Doorstep" not in prof["services"]
    assert "Tap and mixer repair" in prof["services"]


def test_audience_specific_not_template():
    from app.intel.crawler import parse_html
    from app.intel.profiles import extract_profile

    p = parse_html("https://fixkaro.test/", HTML)
    prof = extract_profile([p], "https://fixkaro.test/")
    aud = prof["target_customer"]
    assert "homeowners" in aud.lower()
    assert "visitors interested in the offering" not in aud


def test_crawl_follows_same_origin_links(monkeypatch):
    from app.intel import crawler

    seen: list[str] = []

    class FakeResp:
        def __init__(self, url: str):
            self.url = url
            if url.rstrip("/") == "https://site.test":
                self.text = ('<html><body><a href="/services">Our Services</a>'
                             '<a href="https://other.test/x">Out</a></body></html>')
            else:
                self.text = "<html><body><h2>Deep Service Page</h2></body></html>"

        def raise_for_status(self):
            return None

    class FakeClient:
        def get(self, url: str):
            seen.append(url)
            return FakeResp(url)

        def close(self):
            return None

    monkeypatch.setattr(crawler, "FETCH_TIMEOUT", 5.0)
    import httpx
    monkeypatch.setattr(httpx, "Client", lambda **kw: FakeClient())
    pages = crawler.crawl_site("https://site.test/", max_pages=5)
    urls = [p.url for p in pages]
    assert any("services" in u for u in urls)
    assert not any("other.test" in u for u in urls)
