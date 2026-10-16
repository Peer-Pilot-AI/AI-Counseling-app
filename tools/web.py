"""
Internet tools: web_search (DuckDuckGo, no key needed) and read_page.

The model can call several at once; the agent runs them in parallel, so
"search 3 angles, read the best pages" is as fast as one round trip.
"""
import ipaddress
import re
import socket
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
MAX_BYTES = 1_500_000
_BLOCKS = ["p", "div", "li", "ul", "ol", "br", "tr", "pre", "section", "article", "blockquote",
           "h1", "h2", "h3", "h4", "h5", "h6", "table", "dt", "dd", "figcaption"]
_http = requests.Session()
_http.headers.update(UA)


# ── search ───────────────────────────────────────────────────────────────
def _search_ddgs(query: str, n: int, kind: str) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS          # older package name
    d = DDGS()
    rows = d.news(query, max_results=n) if kind == "news" else d.text(query, max_results=n)
    return [{"title": r.get("title", ""), "url": r.get("href") or r.get("url", ""),
             "snippet": r.get("body", ""), "date": r.get("date", "")} for r in rows or []]


def _search_html(query: str, n: int) -> list[dict]:
    """Fallback: scrape DuckDuckGo's plain-HTML results page."""
    r = _http.post("https://html.duckduckgo.com/html/", data={"q": query}, timeout=10)
    r.raise_for_status()
    out = []
    for res in BeautifulSoup(r.text, "html.parser").select(".result"):
        a = res.select_one(".result__a")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        sn = res.select_one(".result__snippet")
        out.append({"title": a.get_text(" ", strip=True), "url": href,
                    "snippet": sn.get_text(" ", strip=True) if sn else "", "date": ""})
        if len(out) >= n:
            break
    return out


def web_search(args: dict) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "Error: empty query."
    n = max(1, min(int(args.get("max_results") or 6), 10))
    kind = "news" if args.get("kind") == "news" else "web"
    try:
        rows = _search_ddgs(query, n, kind)
    except Exception:
        rows = []
    if not rows:
        try:
            rows = _search_html(query, n)
        except Exception as e:
            return f"Search failed: {e}"
    if not rows:
        return "No results."
    lines = []
    for i, r in enumerate(rows, 1):
        date = f" ({r['date'][:10]})" if r.get("date") else ""
        lines.append(f"{i}. {r['title']}{date}\n   {r['url']}\n   {r['snippet'][:300]}")
    return "\n".join(lines)


# ── read a page ──────────────────────────────────────────────────────────
def _check_public(url: str) -> None:
    """Refuse non-http(s) URLs and anything that resolves to a private/local address,
    so a prompt-injected page can't make the tool poke at your own network."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("only http(s) URLs are allowed")
    for info in socket.getaddrinfo(p.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("refusing to open a private/local address")


def _fetch(url: str, hops: int = 4):
    for _ in range(hops + 1):
        _check_public(url)
        r = _http.get(url, timeout=(5, 12), stream=True, allow_redirects=False)
        if r.is_redirect and r.headers.get("Location"):
            url = urljoin(url, r.headers["Location"])
            r.close()
            continue
        r.raise_for_status()
        return r
    raise ValueError("too many redirects")


def read_page(args: dict) -> str:
    url = (args.get("url") or "").strip()
    start = max(0, int(args.get("start") or 0))
    limit = max(500, min(int(args.get("max_chars") or 6000), 12000))
    if not url:
        return "Error: no url."
    try:
        r = _fetch(url)
        ctype = r.headers.get("Content-Type", "").lower()
        if not (ctype.startswith("text/") or "html" in ctype or "xml" in ctype or "json" in ctype or not ctype):
            return f"Can't read this content type ({ctype.split(';')[0]}); only text/HTML pages."
        raw = b""
        for chunk in r.iter_content(65536):
            raw += chunk
            if len(raw) > MAX_BYTES:
                break
        r.close()
        html = raw.decode(r.encoding or r.apparent_encoding or "utf-8", errors="replace")
    except Exception as e:
        return f"Couldn't open {url}: {e}"

    if "html" in ctype or html.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header",
                         "aside", "form", "iframe"]):
            tag.decompose()
        body = soup.find("article") or soup.find("main") or soup.body or soup
        # Break lines only at block-level elements, so inline tags (links, <code>, <b>)
        # stay inside their sentence instead of each landing on its own line.
        for tag in body.find_all(_BLOCKS):
            tag.insert_before("\n")
            tag.insert_after("\n")
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in body.get_text("").splitlines()]
        text = "\n".join(ln for ln in lines if len(ln) > 2)
    else:
        title, text = "", html.strip()

    total = len(text)
    chunk = text[start:start + limit]
    if not chunk:
        return f"Nothing at offset {start} (page has {total} characters)."
    more = (f"\n[...{total - start - limit} more characters; call read_page again with start={start + limit}]"
            if start + limit < total else "")
    head = f"Title: {title}\nURL: {url}\n\n" if start == 0 else ""
    return head + chunk + more


TOOLS = [
    {"name": "web_search",
     "description": ("Search the internet. Use for anything current or that you may not know: news, prices, "
                     "versions, people, events, facts to verify. Returns titles, URLs and snippets. "
                     "Call it several times in one go with different queries for broad research."),
     "parameters": {"type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query, a few keywords"},
                        "kind": {"type": "string", "enum": ["web", "news"],
                                 "description": "'news' for recent headlines, default 'web'"},
                        "max_results": {"type": "integer", "description": "1-10, default 6"}},
                    "required": ["query"]},
     "run": web_search},
    {"name": "read_page",
     "description": ("Open a web page and return its readable text. Use on the best URLs from web_search "
                     "when snippets aren't enough. For long pages, continue with the 'start' offset."),
     "parameters": {"type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Full http(s) URL"},
                        "start": {"type": "integer", "description": "Character offset to continue from"},
                        "max_chars": {"type": "integer", "description": "Chunk size, default 6000"}},
                    "required": ["url"]},
     "run": read_page},
]