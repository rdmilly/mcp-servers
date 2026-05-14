"""Telegram Bot MCP Server - lightweight Bot API wrapper."""
import os
import httpx
from fastmcp import FastMCP

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

mcp = FastMCP("telegram-bot", instructions="Telegram Bot API for sending/receiving messages")


async def _api(method: str, **kwargs) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/{method}", json=kwargs)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def send_message(text: str, chat_id: str = "", parse_mode: str = "HTML") -> str:
    """Send a message via Telegram bot. Uses default chat_id if not specified."""
    cid = chat_id or DEFAULT_CHAT_ID
    if not cid:
        return "Error: no chat_id provided and TELEGRAM_CHAT_ID not set"
    result = await _api("sendMessage", chat_id=cid, text=text, parse_mode=parse_mode)
    if result.get("ok"):
        msg = result["result"]
        return f"Sent message {msg['message_id']} to chat {cid}"
    return f"Error: {result}"


@mcp.tool()
async def send_document(chat_id: str = "", document_url: str = "", caption: str = "") -> str:
    """Send a document/file via URL to a Telegram chat."""
    cid = chat_id or DEFAULT_CHAT_ID
    if not cid:
        return "Error: no chat_id"
    params = {"chat_id": cid, "document": document_url}
    if caption:
        params["caption"] = caption
        params["parse_mode"] = "HTML"
    result = await _api("sendDocument", **params)
    return f"Sent document to {cid}" if result.get("ok") else f"Error: {result}"


@mcp.tool()
async def get_updates(limit: int = 10, offset: int = 0) -> str:
    """Get recent messages/updates sent TO the bot."""
    params = {"limit": limit, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    result = await _api("getUpdates", **params)
    if not result.get("ok"):
        return f"Error: {result}"
    updates = result.get("result", [])
    if not updates:
        return "No new updates"
    lines = []
    for u in updates:
        msg = u.get("message", {})
        fr = msg.get("from", {})
        txt = msg.get("text", "(no text)")
        lines.append(f"[{u['update_id']}] {fr.get('first_name', '?')}: {txt}")
    return "\n".join(lines)


@mcp.tool()
async def get_chat_info(chat_id: str = "") -> str:
    """Get info about a chat (title, type, member count)."""
    cid = chat_id or DEFAULT_CHAT_ID
    result = await _api("getChat", chat_id=cid)
    if not result.get("ok"):
        return f"Error: {result}"
    c = result["result"]
    return (f"Chat: {c.get('title', c.get('first_name', '?'))}\n"
            f"Type: {c.get('type')}\nID: {c.get('id')}")


@mcp.tool()
async def get_me() -> str:
    """Get bot info (name, username)."""
    result = await _api("getMe")
    if result.get("ok"):
        b = result["result"]
        return f"Bot: {b['first_name']} (@{b.get('username', '?')}), ID: {b['id']}"
    return f"Error: {result}"


@mcp.tool()
async def pin_message(chat_id: str = "", message_id: int = 0) -> str:
    """Pin a message in a chat."""
    cid = chat_id or DEFAULT_CHAT_ID
    result = await _api("pinChatMessage", chat_id=cid, message_id=message_id)
    return "Pinned" if result.get("ok") else f"Error: {result}"


@mcp.tool()
async def set_chat_description(description: str, chat_id: str = "") -> str:
    """Update a chat/channel description."""
    cid = chat_id or DEFAULT_CHAT_ID
    result = await _api("setChatDescription", chat_id=cid, description=description)
    return "Updated" if result.get("ok") else f"Error: {result}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
