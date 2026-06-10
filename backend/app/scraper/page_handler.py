from typing import Optional

from playwright.async_api import Page


async def navigate(page: Page, url: str):
    return await page.goto(url, wait_until="networkidle", timeout=30000)


async def wait_for_selector(page: Page, selector: Optional[str]) -> None:
    if selector:
        await page.wait_for_selector(selector, timeout=10000)


async def scroll_to_bottom(page: Page) -> None:
    await page.evaluate(
        """
        async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 100;
                const timer = setInterval(() => {
                    const scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= scrollHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }
        """
    )
    await page.wait_for_timeout(1500)
