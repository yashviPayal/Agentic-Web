from typing import Any, Dict

from app.scraper.browser import browser_manager


async def browse_web(**kwargs: Any) -> Dict[str, Any]:
    return await browser_manager.browse_web(**kwargs)
