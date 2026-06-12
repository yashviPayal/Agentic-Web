import logging
import urllib.parse
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from app.scraper.browser import browser_manager
from app.scraper.page_handler import navigate, scroll_to_bottom
from app.services.llm_service import get_openai_client
from app.config import settings
from app.tools.extraction_tools import extract_clean_content

logger = logging.getLogger(__name__)


def get_links(html: str, base_url: str) -> List[Dict[str, str]]:
    """
    Extracts all absolute links from HTML, filters out junk links,
    deduplicates them, and returns up to 50 links.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    raw_links = soup.find_all("a", href=True)
    seen_urls = set()
    links = []

    for a in raw_links:
        href = a["href"].strip()
        text = a.get_text(strip=True)

        # Skip anchor, javascript, email, phone, etc.
        if (
            not href
            or href.startswith("#")
            or href.startswith("javascript:")
            or href.startswith("mailto:")
            or href.startswith("tel:")
        ):
            continue

        # Resolve relative URLs
        absolute_url = urllib.parse.urljoin(base_url, href)

        # Parse and filter out non http/https URLs or external CDN links
        parsed = urllib.parse.urlparse(absolute_url)
        if parsed.scheme not in ("http", "https"):
            continue

        # Deduplicate based on URL
        if absolute_url in seen_urls:
            continue

        seen_urls.add(absolute_url)
        links.append({
            "text": text or absolute_url,
            "url": absolute_url
        })

        if len(links) >= 50:
            break

    return links


async def pick_best_link(
    body_links: List[Dict[str, str]],
    nav_links: List[Dict[str, str]],
    intent: str,
) -> Optional[str]:
    """
    Selects the best URL from both body and navigation links matching a user intent.
    First performs a cheap keyword/substring match pre-filter. If exactly one strong match
    is found, returns it immediately. Otherwise, ranks all links by keyword match score,
    preserves and prioritizes nav/tab links, and feeds the top 50 candidates to the LLM router.
    """
    if not body_links and not nav_links:
        return None

    # 1. Combine and flag candidates
    candidate_links = []
    seen = set()

    for l in nav_links:
        url = l["url"].strip()
        if url not in seen:
            seen.add(url)
            candidate_links.append({
                "text": l["text"],
                "url": url,
                "is_nav": True
            })

    for l in body_links:
        url = l["url"].strip()
        if url not in seen:
            seen.add(url)
            candidate_links.append({
                "text": l["text"],
                "url": url,
                "is_nav": False
            })

    # 2. Extract keywords from intent (case-insensitive, remove stop words)
    import re
    words = re.findall(r'\b[a-zA-Z0-9_-]+\b', intent.lower())
    stop_words = {"go", "to", "the", "a", "an", "on", "click", "open", "page", "tab", "link", "find", "show", "get", "with", "into", "for"}
    intent_keywords = [w for w in words if w not in stop_words and len(w) > 1]

    # 3. Cheap pre-filter: if exactly one link matches all keywords in its text or URL, choose it directly
    if intent_keywords:
        strong_matches = []
        for l in candidate_links:
            text_lower = l["text"].lower()
            url_lower = l["url"].lower()
            if all(kw in text_lower or kw in url_lower for kw in intent_keywords):
                strong_matches.append(l)

        if len(strong_matches) == 1:
            logger.info(f"Pre-filter matched exactly one link: {strong_matches[0]['url']}")
            print(f"🎯 [PRE-FILTER MATCH] Found unique matching link: {strong_matches[0]['url']}")
            return strong_matches[0]["url"]

    # 4. Score and rank links by relevance
    scored_candidates = []
    for l in candidate_links:
        score = 0.0
        text_lower = l["text"].lower()
        url_lower = l["url"].lower()
        intent_lower = intent.lower()

        # Exact/phrase matches
        if intent_lower in text_lower:
            score += 100.0
        if intent_lower in url_lower:
            score += 50.0

        # Keyword matches
        for kw in intent_keywords:
            if kw in text_lower:
                score += 10.0
            if kw in url_lower:
                score += 5.0

        # Prioritize navigation/tabs if there is any keyword relevance
        if score > 0.0 and l["is_nav"]:
            score += 20.0

        scored_candidates.append({
            "text": l["text"],
            "url": l["url"],
            "is_nav": l["is_nav"],
            "score": score
        })

    # Sort matching links by score descending
    matching = [c for c in scored_candidates if c["score"] > 0]
    matching.sort(key=lambda x: x["score"], reverse=True)

    non_matching = [c for c in scored_candidates if c["score"] == 0]
    # Prioritize nav links among non-matching
    nav_non_matching = [c for c in non_matching if c["is_nav"]]
    body_non_matching = [c for c in non_matching if not c["is_nav"]]

    ordered_candidates = matching + nav_non_matching + body_non_matching

    # Limit to top 50 links to avoid overwhelming the LLM
    top_candidates = ordered_candidates[:50]

    # If no links matched any keyword, and we have no candidates, return None
    if not top_candidates:
        return None

    # 5. LLM Router Pass
    client = get_openai_client()
    model = settings.openrouter_model

    formatted_links = "\n".join(f"- Text: '{l['text']}' | URL: {l['url']}" for l in top_candidates)

    prompt = (
        "You are a deterministic router agent.\n"
        "Given the user's intent, select the single best matching absolute URL from the list of available links.\n\n"
        "IMPORTANT: Match the intent keywords against the link text AND the URL path/query parameters. "
        "Some tab or navigation links may have generic or empty text, but their URL path/query parameters "
        "contain very specific keywords (e.g. '?tab=repositories' or '/repos'). "
        "Analyze the URL parameters closely to select the correct link.\n\n"
        f"User Intent: \"{intent}\"\n\n"
        "Available Links:\n"
        f"{formatted_links}\n\n"
        "Rules:\n"
        "1. Return ONLY the absolute URL of the selected link from the list.\n"
        "2. Do NOT add any preamble, markdown code blocks, explanation, or extra characters.\n"
        "3. If no link is a good match, return the string \"None\"."
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.0,
        )
        choice = response.choices[0].message.content.strip()
        # Clean any markdown formatting
        if choice.startswith("```"):
            choice = choice.replace("```", "").strip()
        if choice.startswith("url"):
            choice = choice.replace("url", "").strip()
        
        choice = choice.strip("\"'")
        
        if choice.lower() == "none" or not choice.startswith("http"):
            return None

        # Verify the chosen URL actually exists in top_candidates
        chosen_url = next((l["url"] for l in top_candidates if l["url"] == choice), None)
        if chosen_url:
            return chosen_url

        # Fallback substring match
        chosen_url = next((l["url"] for l in top_candidates if choice in l["url"] or l["url"] in choice), None)
        return chosen_url
    except Exception as e:
        logger.error(f"Error picking best link via LLM: {e}")
        return None


async def navigate_page(intent: str, max_depth: int = 5) -> Dict[str, Any]:
    """
    Statefully navigate the current Playwright page to a new URL matching the user's intent.
    """
    page = browser_manager.current_page
    if not page or page.is_closed():
        return {
            "success": False,
            "error": "No active browser session. You must call 'browse_web' before using 'navigate_page'."
        }

    # Initialize depth count on browser_manager if not set
    if not hasattr(browser_manager, "navigation_depth"):
        browser_manager.navigation_depth = 0

    browser_manager.navigation_depth += 1
    if browser_manager.navigation_depth > max_depth:
        return {
            "success": False,
            "error": f"Navigation depth limit ({max_depth}) exceeded. Please extract whatever data you have collected."
        }

    html = await page.content()
    base_url = page.url

    # Extract clean links using extract_clean_content
    _, body_links, nav_links = extract_clean_content(html, base_url=base_url)
    if not body_links and not nav_links:
        return {
            "success": False,
            "error": "No clickable links found on the current page."
        }

    target_url = await pick_best_link(body_links, nav_links, intent)
    if not target_url:
        return {
            "success": False,
            "error": f"Could not find any link matching navigation intent: '{intent}'."
        }

    # Same-page navigation guard (trailing slash ignored)
    def clean_url_for_compare(url: str) -> str:
        return url.rstrip('/')

    if clean_url_for_compare(target_url) == clean_url_for_compare(base_url):
        return {
            "success": False,
            "error": (
                f"The selected link '{target_url}' is identical to the current page. "
                f"Navigation failed because it would not change the page. "
                f"Please specify a different intent to navigate elsewhere."
            )
        }

    print(f"🔗 [NAVIGATING] Found matching URL: {target_url}. Navigating page...")
    logger.info(f"Navigating to {target_url} matching intent '{intent}'")

    try:
        response = await navigate(page, target_url)
        await scroll_to_bottom(page)

        title = await page.title()
        html_content = await page.content()

        result: Dict[str, Any] = {
            "url": target_url,
            "title": title,
            "status": response.status if response else 200,
            "success": True,
        }

        # Consistent contract with browse_web
        content, extracted_links, next_nav_links = extract_clean_content(
            html_content, base_url=target_url, max_text_length=8000
        )
        result["content"] = content
        result["links"] = extracted_links
        result["navigation_links"] = next_nav_links

        return result
    except Exception as e:
        logger.error(f"Failed navigating to {target_url}: {e}")
        return {
            "success": False,
            "error": f"Failed navigating to {target_url}: {str(e)}"
        }
