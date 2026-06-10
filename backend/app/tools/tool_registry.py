from typing import Any, Awaitable, Callable, Dict, List

from app.tools.browser_tools import browse_web


ToolHandler = Callable[..., Awaitable[Dict[str, Any]]]


def get_tool_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "browse_web",
                "description": (
                    "Browse a website and extract its content. Use this when the user "
                    "asks about a specific website, wants to read a webpage, or needs "
                    "information from a URL."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The full URL to browse, including http:// or https://",
                        },
                        "extract_content": {
                            "type": "boolean",
                            "description": "Whether to extract the main text content",
                            "default": True,
                        },
                        "scroll_page": {
                            "type": "boolean",
                            "description": "Whether to scroll the page to load lazy content",
                            "default": True,
                        },
                    },
                    "required": ["url"],
                },
            },
        }
    ]


TOOL_REGISTRY: Dict[str, ToolHandler] = {
    "browse_web": browse_web,
}


async def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        handler = TOOL_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unknown tool: {name}") from exc

    return await handler(**arguments)
