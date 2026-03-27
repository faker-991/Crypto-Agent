import re

import httpx


class ResearchToolbox:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=10.0, follow_redirects=True)

    def search_web(self, query: str) -> dict:
        try:
            response = self.client.get("https://duckduckgo.com/html/", params={"q": query})
            response.raise_for_status()
            html = response.text
            title_matches = re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            snippet_matches = re.findall(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            results = []
            for index, (url, raw_title) in enumerate(title_matches[:10]):
                snippet_pair = snippet_matches[index] if index < len(snippet_matches) else ("", "")
                snippet = snippet_pair[0] or snippet_pair[1]
                results.append(
                    {
                        "title": self._clean_html(raw_title),
                        "url": self._clean_url(url),
                        "snippet": self._clean_html(snippet),
                    }
                )
            return {"status": "success", "query": query, "results": results}
        except Exception as exc:
            return {"status": "failed", "query": query, "results": [], "error": str(exc)}

    def fetch_page(self, url: str) -> dict:
        try:
            response = self.client.get(url)
            response.raise_for_status()
            html = response.text
            title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
            text = self._extract_text(html)
            return {
                "status": "success",
                "url": url,
                "title": self._clean_html(title_match.group(1)) if title_match else url,
                "text": text,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "url": url,
                "title": "",
                "text": "",
                "error": str(exc),
            }

    def _extract_text(self, html: str) -> str:
        stripped = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        stripped = re.sub(r"<style.*?</style>", " ", stripped, flags=re.IGNORECASE | re.DOTALL)
        stripped = re.sub(r"<[^>]+>", " ", stripped)
        return self._clean_html(stripped)

    def _clean_html(self, text: str) -> str:
        cleaned = re.sub(r"&nbsp;|&#160;", " ", text)
        cleaned = re.sub(r"&amp;", "&", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _clean_url(self, url: str) -> str:
        if url.startswith("//"):
            return f"https:{url}"
        return url
