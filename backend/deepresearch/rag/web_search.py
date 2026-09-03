"""Web search + page fetching.

Search backends (selected by get_search_backend() based on settings):
  - MockSearch       : deterministic fake results, offline-only (USE_MOCK_SEARCH=true)
  - TavilySearch     : AI-optimized real search, best quality (needs SEARCH_API_KEY)
  - DuckDuckGoSearch : real web results via the HTML endpoint, no API key needed

Selection logic:
  use_mock_search=true        → MockSearch
  search_api_key configured   → TavilySearch (falls back to DDG on failure)
  otherwise                   → DuckDuckGoSearch (falls back to MockSearch on failure)

Page fetching:
  - fetch_page(url) → strips HTML, returns plain text (≤ 8000 chars)
"""

from __future__ import annotations

import html as _html
import re
import urllib.parse
from dataclasses import dataclass
from functools import lru_cache

import httpx

from deepresearch.common.logging import get_logger

log = get_logger("rag.web_search")

# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str

    def to_text(self) -> str:
        return f"[{self.title}]\nURL: {self.url}\n{self.snippet}"


def _strip_tags(fragment: str) -> str:
    """Remove HTML tags and unescape entities from a small HTML fragment."""
    text = re.sub(r"<[^>]+>", "", fragment)
    return _html.unescape(text).strip()


# ── Mock search ────────────────────────────────────────────────────────────────

_MOCK_SOURCES = [
    ("https://example.com/article-a", "深度分析：{query}的现状与趋势", "根据最新数据，{query}领域正经历显著变化。专家指出，核心驱动力包括技术创新、政策支持与市场需求三方面。"),
    ("https://wiki.example.com/{slug}", "维基百科：{query}综述", "{query}是指……（Mock 维基词条）。该领域起源于20世纪，近年来随着AI与数字化加速发展。"),
    ("https://news.example.com/2026/{slug}", "2026年{query}行业报告摘要", "行业报告显示，{query}市场规模预计在2026年达到XXX亿元，年复合增长率约为YY%。"),
    ("https://research.example.com/{slug}", "{query}学术综述", "本文系统梳理了{query}的研究脉络，归纳了核心争议与未来方向。"),
    ("https://blog.example.com/{slug}", "实践者视角：如何理解{query}", "作为从业者，我认为{query}最关键的挑战在于……（Mock 博客内容）"),
]

class MockSearch:
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        slug = re.sub(r"[^\w]", "-", query)[:30].lower()
        results = []
        for url_tpl, title_tpl, snippet_tpl in _MOCK_SOURCES[:max_results]:
            results.append(SearchResult(
                url=url_tpl.format(slug=slug),
                title=title_tpl.format(query=query),
                snippet=snippet_tpl.format(query=query),
            ))
        log.info("mock_search", query=query, results=len(results))
        return results


# ── DuckDuckGo search (real HTML endpoint, no API key) ─────────────────────────

class DuckDuckGoSearch:
    """Real web search via DuckDuckGo's HTML endpoint (no API key needed).

    Parses html.duckduckgo.com/html/ — this returns actual organic web results
    (real titles, real URLs, real snippets), unlike the Instant-Answer JSON API
    which only contains encyclopedia-style answers and is empty for most queries.
    """

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    _RESULT_RE = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.DOTALL,
    )
    _SNIPPET_RE = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.DOTALL,
    )

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(
                timeout=15, headers=self._HEADERS, follow_redirects=True
            ) as client:
                resp = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query, "kl": "wt-wt"},
                )
                resp.raise_for_status()
                page = resp.text
        except Exception as exc:
            log.warning("ddg_html_failed", error=str(exc))
            return []   # 真实模式下宁可返回空，也绝不退化到 mock 假数据

        urls = self._RESULT_RE.findall(page)
        snippets = self._SNIPPET_RE.findall(page)

        results: list[SearchResult] = []
        for i, (raw_url, raw_title) in enumerate(urls):
            if len(results) >= max_results:
                break
            url = self._clean_url(raw_url)
            if not url:
                continue
            snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
            results.append(SearchResult(
                url=url, title=_strip_tags(raw_title), snippet=snippet
            ))

        if not results:
            log.info("ddg_html_no_results", query=query)
            return []   # 无结果返回空，避免假数据污染（worker 会换查询重试）

        log.info("ddg_html_search", query=query, results=len(results))
        return results

    @staticmethod
    def _clean_url(raw: str) -> str:
        # DDG wraps outbound links as //duckduckgo.com/l/?uddg=<encoded>&...
        if "uddg=" in raw:
            try:
                full = raw if raw.startswith("http") else "https:" + raw
                qs = urllib.parse.urlparse(full).query
                params = urllib.parse.parse_qs(qs)
                if "uddg" in params:
                    return urllib.parse.unquote(params["uddg"][0])
            except Exception:
                return ""
        if raw.startswith("//"):
            return "https:" + raw
        if raw.startswith("http"):
            return raw
        return ""


# ── Tavily search (high quality, API key) ──────────────────────────────────────

class TavilySearch:
    """AI-optimized web search via the Tavily REST API.

    Returns real URLs with relevance-ranked content excerpts — the best-quality
    backend. Requires SEARCH_API_KEY (free tier at https://tavily.com).
    """

    def __init__(self, api_key: str, api_url: str = "https://api.tavily.com") -> None:
        self._api_key = api_key
        self._url = api_url.rstrip("/") + "/search"

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(self._url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.warning("tavily_failed_fallback_ddg", error=str(exc))
            return await DuckDuckGoSearch().search(query, max_results)

        results: list[SearchResult] = []
        for item in data.get("results", [])[:max_results]:
            url = item.get("url", "")
            if not url:
                continue
            results.append(SearchResult(
                url=url,
                title=(item.get("title") or "")[:120],
                snippet=item.get("content") or "",
            ))

        if not results:
            log.info("tavily_no_results_fallback_ddg", query=query)
            return await DuckDuckGoSearch().search(query, max_results)

        log.info("tavily_search", query=query, results=len(results))
        return results


# ── Page fetcher ───────────────────────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s{3,}")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)

MAX_PAGE_CHARS = 8000


async def fetch_page(url: str, timeout: int = 12) -> str:
    """Fetch a URL and return stripped plain text (≤ MAX_PAGE_CHARS chars)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; DeepResearchBot/1.0)"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            page = resp.text
    except Exception as exc:
        raise RuntimeError(f"fetch_page failed for {url}: {exc}") from exc

    # Strip scripts/styles first, then tags
    page = _SCRIPT_RE.sub(" ", page)
    text = _TAG_RE.sub(" ", page)
    text = _html.unescape(text)
    text = _SPACE_RE.sub("\n", text).strip()

    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS] + "\n…[内容截断]"

    log.info("fetch_page", url=url, chars=len(text))
    return text


# ── Factory ───────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_search_backend():
    from deepresearch.config.settings import get_settings
    cfg = get_settings()
    if cfg.use_mock_search:
        log.info("search_backend", backend="mock")
        return MockSearch()
    if cfg.search_api_key:
        log.info("search_backend", backend="tavily")
        return TavilySearch(cfg.search_api_key, cfg.search_api_url)
    log.info("search_backend", backend="duckduckgo_html")
    return DuckDuckGoSearch()
