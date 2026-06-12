import logging
from typing import Dict, List

from app.agents.web_agent import agent
from app.scraper.browser import browser_manager

logger = logging.getLogger(__name__)


class AgentService:
    async def chat(self, messages: List[Dict[str, str]]) -> dict:
        try:
            return await agent.chat(messages)
        finally:
            logger.info("Closing browser context/session at the end of chat request")
            await browser_manager.close()


agent_service = AgentService()
