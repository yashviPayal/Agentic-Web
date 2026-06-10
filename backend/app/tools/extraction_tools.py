from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup


def extract_clean_content(
    html_content: str,
    max_text_length: int = 8000,
) -> Tuple[str, List[Dict[str, Any]]]:
    soup = BeautifulSoup(html_content, "lxml")

    for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        element.decompose()

    main_content = soup.find("article") or soup.find("main") or soup.find("div", class_="content")
    text_source = main_content if main_content else soup
    text = text_source.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    original_length = len(text)
    if original_length > max_text_length:
        text = text[:max_text_length] + f"\n\n[Content truncated. Total length: {original_length} characters]"

    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if href.startswith("http"):
            links.append({"text": anchor.get_text(strip=True), "url": href})

    return text, links[:20]
