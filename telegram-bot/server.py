"""Telegram Bot MCP Server — send/receive messages via Telegram Bot API.
Tools: send_message, get_updates, get_chat_info, send_document, send_photo, get_me
"""
import os, json
import httpx
from mcp.server.fastmcp import FastMCP

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
mcp = FastMCP("telegram-bot")
client = httpx.AsyncClient(timeout=30)

async def _tg(method, **kwargs): resp = await client.post(f"{BASE_URL}/{method}", json=kwargs); return resp.json()

@mcp.tool()
async def send_message(text: str, chat_id: str = "", parse_mode: str = "Markdown") -> str:
    """Send a message to a Telegram chat."""
    cid = chat_id or DEFAULT_CHAT_ID
    if not cid: return "Error: No chat_id provided and no default set"
    result = await _tg("sendMessage", chat_id=cid, text=text, parse_mode=parse_mode)
    if result.get("ok"): msg = result["result"]; return f"Message sent (id: {msg['message_id']}) to chat {cid}"
    return f"Error: {result.get('description', 'Unknown error')}"

@mcp.tool()
async def get_updates(limit: int = 20, offset: int = 0) -> str:
    """Get recent messages/updates received by the bot."""
    result = await _tg("getUpdates", limit=limit, offset=offset)
    if not result.get("ok"): return f"Error: {result.get('description')}"
    updates = result.get("result", [])
    if not updates: return "No new updates"
    lines = []
    for u in updates:
        msg = u.get("message", {}); frm = msg.get("from", {})
        lines.append(f"[{u['update_id']}] {frm.get('first_name', 'Unknown')}: {msg.get('text', '(no text)')}")
    return "\n".join(lines)

@mcp.tool()
async def get_chat_info(chat_id: str = "") -> str:
    """Get information about a chat."""
    cid = chat_id or DEFAULT_CHAT_ID
    result = await _tg("getChat", chat_id=cid)
    return json.dumps(result["result"], indent=2) if result.get("ok") else f"Error: {result.get('description')}"

@mcp.tool()
async def send_document(file_url: str, caption: str = "", chat_id: str = "") -> str:
    """Send a document/file to a Telegram chat via URL."""
    cid = chat_id or DEFAULT_CHAT_ID
    params = {"chat_id": cid, "document": file_url}
    if caption: params["caption"] = caption
    result = await _tg("sendDocument", **params)
    return f"Document sent to chat {cid}" if result.get("ok") else f"Error: {result.get('description')}"

@mcp.tool()
async def send_photo(photo_url: str, caption: str = "", chat_id: str = "") -> str:
    """Send a photo to a Telegram chat via URL."""
    cid = chat_id or DEFAULT_CHAT_ID
    params = {"chat_id": cid, "photo": photo_url}
    if caption: params["caption"] = caption
    result = await _tg("sendPhoto", **params)
    return f"Photo sent to chat {cid}" if result.get("ok") else f"Error: {result.get('description')}"

@mcp.tool()
async def get_me() -> str:
    """Get bot info (name, username, etc)."""
    result = await _tg("getMe")
    return json.dumps(result["result"], indent=2) if result.get("ok") else f"Error: {result.get('description')}"

if __name__ == "__main__": mcp.run(transport="stdio")
