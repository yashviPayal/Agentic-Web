import os
import logging
from typing import Any, Dict
from datetime import datetime
from app.scraper.browser import browser_manager
from app.scraper.screenshot import capture_screenshot_base64
from app.config import settings

logger = logging.getLogger(__name__)


async def take_screenshot() -> Dict[str, Any]:
    """
    Capture a screenshot of the current page.
    Saves to a local file if configured, otherwise returns base64.
    """
    page = browser_manager.current_page
    if not page or page.is_closed():
        return {
            "success": False,
            "error": "No active browser session. Call browse_web first."
        }
    
    try:
        if settings.save_screenshots_local:
            screenshots_dir = os.path.join(os.path.dirname(__file__), "..", "..", "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.abspath(os.path.join(screenshots_dir, filename))
            
            await page.screenshot(path=filepath, full_page=False)
            return {
                "success": True,
                "message": f"Screenshot saved locally to {filepath}",
                "filepath": filepath
            }
        else:
            base64_img = await capture_screenshot_base64(page)
            return {
                "success": True,
                "message": "Screenshot captured as base64 (omitted from logs for brevity). Check frontend or use local save setting.",
                # "base64": base64_img
            }
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return {"success": False, "error": f"Screenshot failed: {str(e)}"}
