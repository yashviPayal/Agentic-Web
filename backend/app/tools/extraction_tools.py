import json
import logging
from typing import Any, Dict, List, Tuple
from bs4 import BeautifulSoup
from app.services.llm_service import get_openai_client
from app.config import settings

logger = logging.getLogger(__name__)


def extract_clean_content(
    html_content: str,
    max_text_length: int = 8000,
) -> Tuple[str, List[Dict[str, Any]]]:
    try:
        soup = BeautifulSoup(html_content, "lxml")
    except Exception:
        soup = BeautifulSoup(html_content, "html.parser")

    for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        element.decompose()

    main_content = soup.find("article") or soup.find("main") or soup.body
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


def clean_html(raw_html: str) -> str:
    """Strips scripts, styles, nav, footer, header, aside, noscript elements and returns plain text with normalized whitespace."""
    try:
        soup = BeautifulSoup(raw_html, "lxml")
    except Exception:
        soup = BeautifulSoup(raw_html, "html.parser")

    for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        element.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def score_and_chunk(text: str, fields: List[str]) -> List[str]:
    """Splits text into overlapping chunks of ~2000 characters and returns the top 3 chunks."""
    chunk_size = 2000
    overlap = 500
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start += chunk_size - overlap

    fields_lower = [f.lower() for f in fields]
    scored_chunks = []

    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = 0
        for f in fields_lower:
            # Score based on keyword occurrence
            score += chunk_lower.count(f)
            # Extra weight if terms like currency symbols or numbers are present in the same chunk
            if f == "price" or "price" in f:
                if any(c in chunk for c in ["₹", "$", "Rs", "rs"]):
                    score += 5
            if f == "rating" or "rating" in f:
                if any(str(i) in chunk for i in range(10)):
                    score += 2
            if f == "availability" or "availability" in f:
                if "stock" in chunk_lower or "avail" in chunk_lower:
                    score += 5
                    
        scored_chunks.append((score, chunk))

    # Sort descending by score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [chunk for score, chunk in scored_chunks[:3]]



async def llm_extract(chunks: List[str], fields: List[str]) -> Dict[str, Any]:
    """Sends the top chunks to the LLM to extract the requested fields as JSON."""
    client = get_openai_client()
    text_content = "\n\n".join(chunks)

    system_prompt = (
        "You are an expert data extraction assistant.\n"
        "Extract the requested fields from the provided text.\n"
        "Return ONLY a valid JSON object where keys are the requested fields and values are the extracted details.\n"
        "If a field is not present in the text, use null as the value.\n"
        "Do not include any markdown formatting or backticks (like ```json). Return ONLY the raw JSON string."
    )
    user_prompt = f"Fields to extract: {fields}\n\nText:\n{text_content}"

    try:
        response = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()

        # Strip markdown code blocks if the model returned them
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.error(f"Failed to extract fields with LLM: {e}")

    return {}


def text_extract_fallback(text: str, fields: List[str]) -> Dict[str, Any]:
    results = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines_lower = [line.lower() for line in lines]
    
    for field in fields:
        field_lower = field.lower()
        value = None
        
        # Look for the field in the lines
        for idx, line in enumerate(lines_lower):
            if field_lower in line:
                # Often the value is on the next line or two
                for offset in range(1, 4):
                    if idx + offset < len(lines):
                        next_line = lines[idx + offset]
                        # For price
                        if "price" in field_lower:
                            if any(c in next_line for c in ["₹", "$", "Rs", "rs"]):
                                value = next_line
                                break
                        # For rating
                        elif "rating" in field_lower or "rate" in field_lower:
                            # Check the line immediately before (e.g. "4.6" before "Ratings")
                            if idx - 1 >= 0:
                                prev_line = lines[idx - 1]
                                if any(char.isdigit() for char in prev_line) and "." in prev_line and len(prev_line) < 10:
                                    value = prev_line
                                    break
                            if any(char.isdigit() for char in next_line) and "%" not in next_line and "off" not in next_line.lower():
                                value = next_line
                                break
                        # For availability
                        elif "availability" in field_lower or "stock" in field_lower:
                            if any(term in next_line.lower() for term in ["stock", "avail", "notify", "order"]):
                                value = next_line
                                break
                if value:
                    break
                    
        # Special check for common standalone patterns if not found
        if not value:
            if "price" in field_lower:
                # Find lines with currency symbol
                for line in lines:
                    if any(c in line for c in ["₹", "$"]) and any(char.isdigit() for char in line):
                        if len(line) < 30:
                            value = line
                            break
            elif "rating" in field_lower:
                for line in lines:
                    # Look for standalone rating numbers like "4.6"
                    if len(line) < 10 and "." in line:
                        parts = line.split(".")
                        if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().split()[0].isdigit():
                            value = line
                            break
            elif "availability" in field_lower:
                for idx, line in enumerate(lines_lower):
                    if "stock" in line or "avail" in line or "notify" in line:
                        value = lines[idx]
                        break
                        
        if value:
            results[field] = value
            
    return results


def html_extract(raw_html: str, fields: List[str]) -> Dict[str, Any]:
    """Tries to extract structured fields using BeautifulSoup class names, tables, and meta tags."""
    # Check if raw_html is actually HTML
    is_html = raw_html.strip().startswith("<") or "</" in raw_html
    if not is_html:
        return text_extract_fallback(raw_html, fields)

    try:
        soup = BeautifulSoup(raw_html, "lxml")
    except Exception:
        soup = BeautifulSoup(raw_html, "html.parser")

    results = {}
    for field in fields:
        field_lower = field.lower()
        value = None

        # 1. Meta tag check
        meta_tags = soup.find_all("meta")
        for tag in meta_tags:
            name = tag.get("name", "").lower()
            prop = tag.get("property", "").lower()
            if field_lower in name or field_lower in prop:
                val = tag.get("content")
                if val:
                    value = val.strip()
                    break

        if value:
            results[field] = value
            continue

        # 2. Table check
        th_elements = soup.find_all("th")
        for th in th_elements:
            th_text = th.get_text(strip=True).lower()
            if field_lower in th_text:
                parent_tr = th.find_parent("tr")
                if parent_tr:
                    tds = parent_tr.find_all("td")
                    if tds:
                        value = tds[-1].get_text(strip=True)
                        break

        if value:
            results[field] = value
            continue

        # 3. Class check (elements with class name matching the field name)
        class_elements = soup.find_all(class_=True)
        for el in class_elements:
            classes = [c.lower() for c in el.get("class", [])]
            if any(field_lower in c for c in classes):
                val_text = el.get_text(strip=True)
                if val_text and len(val_text) < 150:
                    value = val_text
                    break

        if value:
            results[field] = value
            continue

        # 4. Heading check if field is title
        if "title" in field_lower or "heading" in field_lower:
            h1 = soup.find("h1")
            if h1:
                value = h1.get_text(strip=True)

        if value:
            results[field] = value

    return results


async def extract_data(page_content: str, fields: List[str]) -> Dict[str, Any]:
    """
    Extract specific fields from webpage content using a two-pass strategy:
    1. HTML parsing pass (meta tags, tables, headings, class matching) -> high confidence.
    2. LLM pass (for unstructured or complex content) -> medium confidence.
    """
    cleaned_text = clean_html(page_content)
    html_results = html_extract(page_content, fields)

    missing_fields = [f for f in fields if f not in html_results or not html_results[f]]
    llm_results = {}

    if missing_fields:
        chunks = score_and_chunk(cleaned_text, missing_fields)
        if chunks:
            llm_results = await llm_extract(chunks, missing_fields)

    data = {}
    confidence = {}

    for field in fields:
        if field in html_results and html_results[field]:
            data[field] = html_results[field]
            confidence[field] = "high"
        elif field in llm_results and llm_results[field]:
            data[field] = llm_results[field]
            confidence[field] = "medium"
        else:
            data[field] = None
            confidence[field] = None

    return {
        "success": True,
        "data": data,
        "confidence": confidence
    }
