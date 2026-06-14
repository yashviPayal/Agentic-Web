import base64

from playwright.async_api import Page


async def capture_screenshot_base64(page: Page) -> str:
    screenshot_bytes = await page.screenshot(full_page=True)
    return base64.b64encode(screenshot_bytes).decode()
