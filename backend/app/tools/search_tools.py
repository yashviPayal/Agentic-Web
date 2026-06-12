import logging
from urllib.parse import parse_qs, urlparse
import httpx
from bs4 import BeautifulSoup
from app.config import settings

logger = logging.getLogger(__name__)


async def search_ddg_fallback(query: str, count: int = 5):
    logger.info(f"Tavily search failed or is missing. Falling back to DuckDuckGo scraping for: '{query}'")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=12.0)
            response.raise_for_status()
            
            try:
                soup = BeautifulSoup(response.text, "lxml")
            except Exception:
                soup = BeautifulSoup(response.text, "html.parser")
            results = []
            
            for r in soup.select(".result")[:count]:
                title_el = r.select_one(".result__title")
                snippet_el = r.select_one(".result__snippet")
                
                title = title_el.get_text(strip=True) if title_el else ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                
                link_el = r.select_one(".result__title a")
                if link_el and link_el.has_attr("href"):
                    actual_url = link_el["href"]
                    if "/l/?uddg=" in actual_url:
                        parsed = urlparse(actual_url)
                        query_params = parse_qs(parsed.query)
                        if "uddg" in query_params:
                            actual_url = query_params["uddg"][0]
                    
                    results.append({
                        "url": actual_url,
                        "title": title,
                        "snippet": snippet,
                    })
            return results
    except Exception as e:
        logger.error(f"DuckDuckGo fallback search failed: {e}")
        return []


async def search_web(query: str, count: int = 5):
    """
    Search the internet for current, real-time,
    recent, product, pricing, company,
    news, release, availability and factual information.

    Always use this tool when the user asks
    about current prices, current events,
    recent releases, product availability,
    or information that may have changed.
    """
    api_key = settings.tavily_api_key
    if not api_key:
        logger.warning("Tavily API key is missing. Using DuckDuckGo fallback.")
        return await search_ddg_fallback(query, count)

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": count,
    }

    logger.info(f"Querying Tavily Search API with query: '{query}', max_results: {count}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=15.0)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "url": item.get("url"),
                "title": item.get("title"),
                "snippet": item.get("content"),
            })

        logger.info(f"Tavily Search API returned {len(results)} results")
        return results
    except Exception as e:
        logger.warning(f"Tavily Search API failed: {e}. Falling back to DuckDuckGo search...")
        return await search_ddg_fallback(query, count)
