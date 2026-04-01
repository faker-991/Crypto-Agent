import json
import httpx
from pathlib import Path

from app.agents.tools.research_tools import ResearchToolbox


def test_search_web_returns_normalized_results() -> None:
    html = """
    <html>
      <body>
        <a class="result__a" href="https://example.com/a">SUI tokenomics overview</a>
        <a class="result__snippet">A summary of tokenomics and ecosystem progress.</a>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.search_web("SUI tokenomics")

    assert result["status"] == "success"
    assert result["results"][0]["title"] == "SUI tokenomics overview"
    assert result["results"][0]["url"] == "https://example.com/a"


def test_search_web_uses_exa_when_api_key_is_configured(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://exa.test/search"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["excludeDomains"] == ["exa.ai"]
            assert payload["category"] == "news"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "BTC market outlook",
                            "url": "https://example.com/btc-outlook",
                            "text": "Macro catalysts and ETF flows.",
                        }
                    ]
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("EXA_API_URL", "https://exa.test/search")
    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.search_web("BTC outlook")

    assert result["status"] == "success"
    assert result["provider"] == "exa"
    assert result["results"][0]["title"] == "BTC market outlook"
    assert result["results"][0]["url"] == "https://example.com/btc-outlook"


def test_search_web_falls_back_to_duckduckgo_when_exa_fails(monkeypatch) -> None:
    html = """
    <html>
      <body>
        <a class="result__a" href="https://example.com/btc-fallback">BTC fallback source</a>
        <a class="result__snippet">Fallback summary from DuckDuckGo.</a>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://exa.test/search"):
            return httpx.Response(500, json={"error": "boom"})
        if request.url.host == "duckduckgo.com":
            return httpx.Response(200, text=html)
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("EXA_API_URL", "https://exa.test/search")
    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.search_web("BTC fallback")

    assert result["status"] == "success"
    assert result["provider"] == "duckduckgo"
    assert result["results"][0]["url"] == "https://example.com/btc-fallback"
    assert result["providers_tried"] == ["exa", "duckduckgo"]


def test_search_web_falls_back_to_duckduckgo_when_exa_returns_empty(monkeypatch) -> None:
    html = """
    <html>
      <body>
        <a class="result__a" href="https://example.com/btc-news">BTC news source</a>
        <a class="result__snippet">Fallback result after Exa returned empty.</a>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://exa.test/search"):
            return httpx.Response(200, json={"results": []})
        if request.url.host == "duckduckgo.com":
            return httpx.Response(200, text=html)
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("EXA_API_URL", "https://exa.test/search")
    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.search_web("BTC news")

    assert result["status"] == "success"
    assert result["provider"] == "duckduckgo"
    assert result["fallback_reason"] == "exa_empty_results"
    assert result["providers_tried"] == ["exa", "duckduckgo"]
    assert result["results"][0]["url"] == "https://example.com/btc-news"


def test_search_web_uses_exa_key_from_env_file_when_process_env_is_empty(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EXA_API_KEY=env-file-exa-key\nEXA_API_URL=https://exa.test/search\n", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://exa.test/search"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "BTC market sentiment",
                            "url": "https://example.com/btc-sentiment",
                            "text": "Risk appetite improved after ETF inflows.",
                        }
                    ]
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_URL", raising=False)
    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)), env_file=env_file)

    result = toolbox.search_web("BTC sentiment")

    assert result["status"] == "success"
    assert result["provider"] == "exa"
    assert result["results"][0]["url"] == "https://example.com/btc-sentiment"


def test_fetch_page_uses_exa_contents_when_api_key_is_configured(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://exa.test/contents"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["urls"] == ["https://example.com/btc-news"]
            assert payload["text"] is True
            assert payload["maxAgeHours"] == 24
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://example.com/btc-news",
                            "title": "BTC News",
                            "text": "Bitcoin sentiment improved after ETF inflows while macro risks remained elevated.",
                            "summary": "BTC news summary",
                        }
                    ]
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("EXA_CONTENTS_API_URL", "https://exa.test/contents")
    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.fetch_page("https://example.com/btc-news")

    assert result["status"] == "success"
    assert result["strategy"] == "exa_contents"
    assert "ETF inflows" in result["text"]


def test_fetch_page_returns_normalized_page_content() -> None:
    html = """
    <html>
      <head><title>SUI Research</title></head>
      <body><main>SUI ecosystem catalysts and risks.</main></body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.fetch_page("https://example.com/sui")

    assert result["status"] == "success"
    assert result["title"] == "SUI Research"
    assert "catalysts" in result["text"].lower()
    assert result["strategy"] == "simple_http"
    assert result["fallback_count"] == 0
    assert result["attempts"][0]["status"] == "success"


def test_fetch_page_returns_failure_payload_instead_of_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.fetch_page("https://example.com/fail")

    assert result["status"] == "failed"
    assert result["text"] == ""
    assert result["attempts"][-1]["failure_reason"] == "http_error"


def test_fetch_page_falls_back_to_readability_like_extractor() -> None:
    html = """
    <html>
      <head><title>Loading...</title></head>
      <body>
        <div>Please enable JavaScript to view this page.</div>
        <script type="application/ld+json">
          {"headline":"BTC Sentiment Update","articleBody":"Bitcoin sentiment improved after ETF inflows and rising institutional demand pushed market optimism higher."}
        </script>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.fetch_page("https://example.com/btc-sentiment")

    assert result["status"] == "success"
    assert result["strategy"] == "readability_like"
    assert result["fallback_count"] == 1
    assert result["attempts"][0]["status"] == "failed"
    assert result["attempts"][0]["failure_reason"] == "dynamic_page_not_rendered"
    assert result["attempts"][1]["status"] == "success"
    assert "institutional demand" in result["text"].lower()
