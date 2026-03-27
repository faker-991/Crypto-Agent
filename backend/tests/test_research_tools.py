import httpx

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


def test_fetch_page_returns_failure_payload_instead_of_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    toolbox = ResearchToolbox(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = toolbox.fetch_page("https://example.com/fail")

    assert result["status"] == "failed"
    assert result["text"] == ""
