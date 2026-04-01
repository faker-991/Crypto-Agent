import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from app.runtime.tool_contracts import ToolSpec

if TYPE_CHECKING:
    from app.clients.mcp_registry import MCPToolRegistry


class ResearchToolbox:
    def __init__(
        self,
        client: httpx.Client | None = None,
        mcp_registry: "MCPToolRegistry | None" = None,
        env_file: Path | None = None,
    ) -> None:
        self.client = client or httpx.Client(timeout=10.0, follow_redirects=True)
        self.mcp_registry = mcp_registry
        self._env_values = self._read_env_file(env_file or Path(__file__).resolve().parents[3] / ".env")

    def search_web(self, query: str) -> dict:
        if self.mcp_registry is not None:
            call = self.mcp_registry.call_tool("research", "search_web", {"query": query})
            if call.error:
                return {"status": "failed", "query": query, "results": [], "error": call.error}
            return call.output
        exa_error: str | None = None
        exa_empty = False
        if self._exa_api_key():
            try:
                exa_payload = self._search_exa(query)
                if exa_payload.get("results"):
                    return exa_payload
                exa_empty = True
            except Exception as exc:
                exa_error = str(exc)
        try:
            results = self._search_duckduckgo(query)
            payload = {
                "status": "success",
                "query": query,
                "results": results,
                "provider": "duckduckgo",
                "providers_tried": ["exa", "duckduckgo"] if self._exa_api_key() else ["duckduckgo"],
            }
            if exa_error:
                payload["fallback_reason"] = exa_error
            elif exa_empty:
                payload["fallback_reason"] = "exa_empty_results"
            return payload
        except Exception as exc:
            error = str(exc)
            if exa_error:
                error = f"exa_failed: {exa_error}; duckduckgo_failed: {error}"
            elif exa_empty:
                error = f"exa_empty_results; duckduckgo_failed: {error}"
            return {"status": "failed", "query": query, "results": [], "error": error, "provider": None}

    def fetch_page(self, url: str) -> dict:
        if self.mcp_registry is not None:
            call = self.mcp_registry.call_tool("research", "fetch_page", {"url": url})
            if call.error:
                return {"status": "failed", "url": url, "title": "", "text": "", "error": call.error}
            return call.output
        if self._exa_api_key():
            try:
                return self._fetch_contents_exa(url)
            except Exception:
                pass
        return PageFetchPipeline(self.client, self._clean_html, self._extract_text).fetch(url)

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

    def _search_exa(self, query: str) -> dict:
        url = self._exa_search_api_url()
        payload = {
            "query": query,
            "numResults": 10,
            "type": "auto",
            "excludeDomains": ["exa.ai"],
        }
        lowered = query.lower()
        if any(token in lowered for token in ("sentiment", "news", "macro", "regulation", "outlook")):
            payload["category"] = "news"
        payload["contents"] = {"highlights": {"maxCharacters": 400}}
        response = self.client.post(
            url,
            headers={
                "x-api-key": self._exa_api_key(),
                "content-type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results", [])
        results = []
        for item in raw_results[:10]:
            if not isinstance(item, dict):
                continue
            results.append(
                {
                    "title": self._clean_html(str(item.get("title") or item.get("url") or "")),
                    "url": self._clean_url(str(item.get("url") or "")),
                    "snippet": self._clean_html(
                        str(
                            item.get("text")
                            or item.get("highlight")
                            or item.get("summary")
                            or item.get("description")
                            or ""
                        )
                    )[:500],
                }
            )
        return {
            "status": "success",
            "query": query,
            "results": results,
            "provider": "exa",
            "providers_tried": ["exa"],
        }

    def _fetch_contents_exa(self, url: str) -> dict:
        response = self.client.post(
            self._exa_contents_api_url(),
            headers={
                "x-api-key": self._exa_api_key(),
                "content-type": "application/json",
            },
            json={
                "urls": [url],
                "text": True,
                "summary": {},
                "maxAgeHours": 24,
            },
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results") or []
        item = raw_results[0] if raw_results else {}
        title = self._clean_html(str(item.get("title") or item.get("url") or url))
        text = self._clean_html(str(item.get("text") or item.get("summary") or ""))
        if len(text.strip()) < 24:
            raise ValueError("exa_contents_empty")
        return {
            "status": "success",
            "url": self._clean_url(str(item.get("url") or url)),
            "title": title,
            "text": text,
            "strategy": "exa_contents",
            "fallback_count": 0,
            "attempts": [
                {
                    "strategy": "exa_contents",
                    "status": "success",
                    "duration_ms": 0.0,
                    "http_status": response.status_code,
                    "content_bytes": len(text.encode("utf-8", errors="ignore")),
                    "text_length": len(text),
                    "failure_reason": None,
                    "title": title,
                }
            ],
        }

    def _exa_api_key(self) -> str:
        return os.getenv("EXA_API_KEY") or self._env_values.get("EXA_API_KEY") or ""

    def _exa_search_api_url(self) -> str:
        return os.getenv("EXA_API_URL") or self._env_values.get("EXA_API_URL") or "https://api.exa.ai/search"

    def _exa_contents_api_url(self) -> str:
        return os.getenv("EXA_CONTENTS_API_URL") or self._env_values.get("EXA_CONTENTS_API_URL") or "https://api.exa.ai/contents"

    def _read_env_file(self, env_file: Path) -> dict[str, str]:
        if not env_file.exists():
            return {}
        values: dict[str, str] = {}
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"' ")
        return values

    def _search_duckduckgo(self, query: str) -> list[dict[str, str]]:
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
        return results


class PageFetchPipeline:
    def __init__(self, client: httpx.Client, clean_html: Any, extract_text: Any) -> None:
        self.client = client
        self._clean_html = clean_html
        self._extract_text = extract_text

    def fetch(self, url: str) -> dict:
        attempts: list[dict[str, Any]] = []
        try:
            response = self.client.get(url, headers={"user-agent": "crypto-agent/1.0"})
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            attempts.append(
                self._attempt(
                    strategy="simple_http",
                    status="failed",
                    http_status=exc.response.status_code,
                    failure_reason="http_error",
                    content_bytes=len(exc.response.text.encode("utf-8", errors="ignore")),
                    title="",
                    text_length=0,
                )
            )
            return self._failed(url, attempts, str(exc))
        except Exception as exc:
            attempts.append(
                self._attempt(
                    strategy="simple_http",
                    status="failed",
                    http_status=None,
                    failure_reason="network_error",
                    content_bytes=0,
                    title="",
                    text_length=0,
                )
            )
            return self._failed(url, attempts, str(exc))

        html = response.text
        http_status = response.status_code
        content_bytes = len(html.encode("utf-8", errors="ignore"))
        simple = self._simple_http_extract(html)
        attempts.append(
            self._attempt(
                strategy="simple_http",
                status="success" if simple["ok"] else "failed",
                http_status=http_status,
                failure_reason=simple["failure_reason"],
                content_bytes=content_bytes,
                title=simple["title"],
                text_length=len(simple["text"]),
            )
        )
        if simple["ok"]:
            return self._success(url, simple["title"], simple["text"], "simple_http", attempts)

        readability = self._readability_like_extract(html)
        attempts.append(
            self._attempt(
                strategy="readability_like",
                status="success" if readability["ok"] else "failed",
                http_status=http_status,
                failure_reason=readability["failure_reason"],
                content_bytes=content_bytes,
                title=readability["title"],
                text_length=len(readability["text"]),
            )
        )
        if readability["ok"]:
            return self._success(url, readability["title"], readability["text"], "readability_like", attempts)
        return self._failed(url, attempts, readability["failure_reason"] or simple["failure_reason"] or "fetch_failed")

    def _simple_http_extract(self, html: str) -> dict[str, Any]:
        title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        title = self._clean_html(title_match.group(1)) if title_match else ""
        text = self._extract_text(html)
        failure_reason = self._classify_failure(title, text)
        return {"ok": failure_reason is None, "title": title, "text": text, "failure_reason": failure_reason}

    def _readability_like_extract(self, html: str) -> dict[str, Any]:
        json_ld = self._extract_json_ld_article(html)
        if json_ld:
            title = json_ld.get("headline") or json_ld.get("title") or ""
            text = self._clean_html(str(json_ld.get("articleBody") or json_ld.get("description") or ""))
            failure_reason = self._classify_failure(title, text, strict=False)
            return {"ok": failure_reason is None, "title": self._clean_html(title), "text": text, "failure_reason": failure_reason}
        article_match = re.search(
            r"<(article|main)[^>]*>(.*?)</(article|main)>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        fragment = article_match.group(2) if article_match else html
        text = self._extract_text(fragment)
        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", fragment, flags=re.IGNORECASE | re.DOTALL)
        title = self._clean_html(title_match.group(1)) if title_match else ""
        failure_reason = self._classify_failure(title, text, strict=False)
        return {"ok": failure_reason is None, "title": title, "text": text, "failure_reason": failure_reason}

    def _extract_json_ld_article(self, html: str) -> dict[str, Any] | None:
        matches = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for raw in matches:
            try:
                payload = json.loads(raw.strip())
            except Exception:
                continue
            candidates = payload if isinstance(payload, list) else [payload]
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                if item.get("articleBody") or item.get("headline") or item.get("description"):
                    return item
        return None

    def _classify_failure(self, title: str, text: str, strict: bool = True) -> str | None:
        combined = f"{title} {text}".lower()
        if any(marker in combined for marker in ("captcha", "verify you are human", "access denied")):
            return "blocked_or_challenged"
        if "enable javascript" in combined or "javascript to view this page" in combined:
            return "dynamic_page_not_rendered"
        min_length = 40 if strict else 24
        if len(text.strip()) < min_length:
            return "empty_content"
        return None

    def _attempt(
        self,
        *,
        strategy: str,
        status: str,
        http_status: int | None,
        failure_reason: str | None,
        content_bytes: int,
        title: str,
        text_length: int,
    ) -> dict[str, Any]:
        return {
            "strategy": strategy,
            "status": status,
            "duration_ms": 0.0,
            "http_status": http_status,
            "content_bytes": content_bytes,
            "text_length": text_length,
            "failure_reason": failure_reason,
            "title": title,
        }

    def _success(self, url: str, title: str, text: str, strategy: str, attempts: list[dict[str, Any]]) -> dict:
        return {
            "status": "success",
            "url": url,
            "title": title or url,
            "text": text,
            "strategy": strategy,
            "fallback_count": max(len(attempts) - 1, 0),
            "attempts": attempts,
        }

    def _failed(self, url: str, attempts: list[dict[str, Any]], error: str) -> dict:
        return {
            "status": "failed",
            "url": url,
            "title": "",
            "text": "",
            "strategy": None,
            "fallback_count": max(len(attempts) - 1, 0),
            "attempts": attempts,
            "error": error,
        }


def build_research_tool_specs() -> list[ToolSpec]:
    return [
        {
            "name": "search_web",
            "server": "research",
            "domain": "research",
            "description": "Search the web for relevant sources.",
            "usage_guidance": "Use for source discovery and evidence gathering.",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "output_schema": {"type": "object", "properties": {}, "required": []},
            "executor_ref": "research.search_web",
            "source_type": "local",
            "audit_level": "basic",
            "replay_mode": "view_only",
        },
        {
            "name": "fetch_page",
            "server": "research",
            "domain": "research",
            "description": "Fetch and normalize a research page.",
            "usage_guidance": "Use when a promising source URL should be inspected directly.",
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            "output_schema": {"type": "object", "properties": {}, "required": []},
            "executor_ref": "research.fetch_page",
            "source_type": "local",
            "audit_level": "basic",
            "replay_mode": "view_only",
        },
        {
            "name": "read_asset_memory",
            "server": "research",
            "domain": "research",
            "description": "Read stored research memory for an asset.",
            "usage_guidance": "Use when previous notes or structured memory might reduce redundant work.",
            "input_schema": {
                "type": "object",
                "properties": {"asset": {"type": "string"}},
                "required": ["asset"],
            },
            "output_schema": {"type": "object", "properties": {}, "required": []},
            "executor_ref": "research.read_asset_memory",
            "source_type": "local",
            "audit_level": "basic",
            "replay_mode": "view_only",
        },
    ]


def build_research_tool_executors(toolbox: ResearchToolbox, memory_root: Path) -> dict[str, Any]:
    def search_web(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
        raw = toolbox.search_web(args["query"])
        status = raw.get("status")
        if status != "success":
            return {
                "status": "failed",
                "output": {"query": raw.get("query"), "results": raw.get("results", [])},
                "output_summary": {"query": raw.get("query"), "results": raw.get("results", [])[:3]},
                "error": raw.get("error", "search_failed"),
                "reason": "search_failed",
                "exception_type": None,
                "degraded": False,
            }
        results = raw.get("results", [])
        return {
            "status": "success",
            "output": raw,
            "output_summary": {
                "query": raw.get("query"),
                "provider": raw.get("provider"),
                "results": [
                    {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "snippet": item.get("snippet"),
                    }
                    for item in results[:5]
                    if isinstance(item, dict)
                ],
            },
            "error": None,
            "reason": None,
            "exception_type": None,
            "degraded": False,
        }

    def fetch_page(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
        raw = toolbox.fetch_page(args["url"])
        status = raw.get("status")
        if status != "success":
            return {
                "status": "failed",
                "output": {"url": raw.get("url"), "title": raw.get("title", ""), "text": raw.get("text", "")},
                "output_summary": {"url": raw.get("url"), "title": raw.get("title", "")},
                "error": raw.get("error", "fetch_failed"),
                "reason": "fetch_failed",
                "exception_type": None,
                "degraded": False,
            }
        return {
            "status": "success",
            "output": raw,
            "output_summary": {
                "url": raw.get("url"),
                "title": raw.get("title"),
                "strategy": raw.get("strategy"),
                "fallback_count": raw.get("fallback_count", 0),
                "text_preview": str(raw.get("text", ""))[:240],
            },
            "error": None,
            "reason": None,
            "exception_type": None,
            "degraded": False,
        }

    def read_asset_memory(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
        asset = str(args["asset"]).upper()
        md_path = memory_root / "assets" / f"{asset}.md"
        json_path = memory_root / "assets" / f"{asset}.json"
        content = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        metadata = {}
        if json_path.exists():
            try:
                import json

                metadata = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                metadata = {}
        output = {"asset": asset, "content": content, "metadata": metadata}
        return {
            "status": "success",
            "output": output,
            "output_summary": {
                "asset": asset,
                "has_markdown": bool(content),
                "metadata_keys": sorted(metadata.keys()),
            },
            "error": None,
            "reason": None,
            "exception_type": None,
            "degraded": False,
        }

    return {
        "research.search_web": search_web,
        "research.fetch_page": fetch_page,
        "research.read_asset_memory": read_asset_memory,
    }
