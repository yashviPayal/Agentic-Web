import logging
from typing import Any, Dict
from app.scraper.browser import browser_manager
from app.tools.extraction_tools import extract_clean_content

logger = logging.getLogger(__name__)


async def scroll(direction: str = "down") -> Dict[str, Any]:
    """
    Scroll the current page up or down.
    Returns the newly visible/extracted content after scrolling.
    """
    page = browser_manager.current_page
    if not page or page.is_closed():
        return {
            "success": False,
            "error": "No active browser session. Call browse_web first."
        }
    
    try:
        if direction.lower() == "down":
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
        elif direction.lower() == "up":
            await page.evaluate("window.scrollBy(0, -window.innerHeight)")
        else:
            return {"success": False, "error": f"Invalid direction: {direction}. Use 'up' or 'down'."}
            
        await page.wait_for_timeout(1000)
        
        html_content = await page.content()
        content, links, nav_links = extract_clean_content(
            html_content, base_url=page.url, max_text_length=8000
        )
        
        return {
            "success": True,
            "message": f"Scrolled {direction} successfully.",
            "url": page.url,
            "content": content,
            "links": links,
            "navigation_links": nav_links,
        }
    except Exception as e:
        logger.error(f"Scroll failed: {e}")
        return {"success": False, "error": f"Scroll failed: {str(e)}"}
