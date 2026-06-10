from fastapi import APIRouter, HTTPException

from app.api.schemas import ChatRequest, ChatResponse, ScrapeRequest
from app.scraper.browser import browser_manager
from app.services.agent_service import agent_service


router = APIRouter()


@router.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


@router.post("/chat/", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest):
    """Chat with the AI agent. It may use browse_web tool automatically."""
    result = await agent_service.chat(request.messages)
    return ChatResponse(**result)


@router.post("/scrape/", tags=["scraping"])
async def scrape(request: ScrapeRequest):
    """Direct scraping endpoint (for testing or direct use)."""
    try:
        result = await browser_manager.browse_web(
            url=str(request.url),
            extract_content=request.extract_content,
            scroll_page=request.scroll_page,
            take_screenshot=request.take_screenshot,
            wait_for=request.wait_for,
            max_text_length=request.max_text_length,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
