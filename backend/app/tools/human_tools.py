import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Shared global state for human interaction
human_request: Dict[str, Any] = {"waiting": False, "prompt": None}
_human_response_queue: asyncio.Queue = asyncio.Queue()

async def request_human_input(prompt: str) -> Dict[str, Any]:
    """
    Pause the agent execution and prompt the human via the frontend.
    Use this when you encounter authentication (login pages, MFA/2FA challenges),
    captchas, or need explicit human guidance to proceed.
    Once the human responds, the agent loop will resume with the response.
    """
    logger.info(f"Pausing agent: human input requested: {prompt}")
    human_request["waiting"] = True
    human_request["prompt"] = prompt

    try:
        # Clear any leftover items in the queue
        while not _human_response_queue.empty():
            _human_response_queue.get_nowait()

        # Wait for the response (timeout of 300 seconds)
        response = await asyncio.wait_for(_human_response_queue.get(), timeout=300)
        return {"success": True, "human_response": response.get("answer", "")}
    except asyncio.TimeoutError:
        logger.warning("Human input timed out.")
        return {"success": False, "error": "Human input timed out after 5 minutes."}
    finally:
        human_request["waiting"] = False
        human_request["prompt"] = None
