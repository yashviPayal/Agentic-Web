from typing import Dict, List

from app.agents.web_agent import agent


class AgentService:
    async def chat(self, messages: List[Dict[str, str]]) -> dict:
        return await agent.chat(messages)


agent_service = AgentService()
