"""mcp-miro — Miro REST API v2 MCP server."""
import os
import httpx
from fastmcp import FastMCP

MIRO_TOKEN = os.environ["MIRO_ACCESS_TOKEN"]
BOARD_ID = os.environ.get("MIRO_BOARD_ID", "uXjVGyXOu5c=")
BASE = "https://api.miro.com/v2"
mcp = FastMCP("miro")
headers = {"Authorization": f"Bearer {MIRO_TOKEN}", "Accept": "application/json", "Content-Type": "application/json"}
client = httpx.Client(base_url=BASE, headers=headers, timeout=30)

def _get(path, **params): r = client.get(path, params=params or None); r.raise_for_status(); return r.json()
def _post(path, json): r = client.post(path, json=json); r.raise_for_status(); return r.json()
def _patch(path, json): r = client.patch(path, json=json); r.raise_for_status(); return r.json()
def _delete(path): r = client.delete(path); r.raise_for_status(); return {"deleted": True}

@mcp.tool()
def get_items(item_type: str = "") -> dict:
    """List all items on the board. item_type: sticky_note, shape, text, frame, connector."""
    params = {"limit": "50"}
    if item_type: params["type"] = item_type
    return _get(f"/boards/{BOARD_ID}/items", **params)

@mcp.tool()
def get_connectors() -> dict:
    """List all connectors (arrows) on the board."""
    return _get(f"/boards/{BOARD_ID}/connectors")

@mcp.tool()
def create_sticky(content: str, x: float = 0, y: float = 0, color: str = "light_yellow", width: float = 200) -> dict:
    """Create a sticky note. Colors: light_yellow, yellow, orange, light_green, green, cyan, light_pink, pink, violet, red, light_blue, blue."""
    return _post(f"/boards/{BOARD_ID}/sticky_notes", {"data": {"content": content, "shape": "square"}, "style": {"fillColor": color}, "position": {"x": x, "y": y, "origin": "center"}, "geometry": {"width": width}})

@mcp.tool()
def bulk_create_stickies(items: list) -> dict:
    """Create multiple stickies. Each item: {content, x, y, color?, width?}"""
    results, errors = [], []
    for item in items:
        try:
            r = client.post(f"/boards/{BOARD_ID}/sticky_notes", json={"data": {"content": item["content"], "shape": "square"}, "style": {"fillColor": item.get("color", "light_yellow")}, "position": {"x": item["x"], "y": item["y"], "origin": "center"}, "geometry": {"width": item.get("width", 200)}})
            r.raise_for_status(); results.append({"content": item["content"], "id": r.json()["id"]})
        except Exception as e: errors.append({"content": item.get("content"), "error": str(e)})
    return {"created": results, "errors": errors}

@mcp.tool()
def create_shape(content: str = "", x: float = 0, y: float = 0, width: float = 200, height: float = 60, shape: str = "rectangle", fill_color: str = "#1a1a1a", text_color: str = "#ffffff") -> dict:
    """Create a shape. shape: rectangle, round_rectangle, circle, triangle, rhombus, etc."""
    return _post(f"/boards/{BOARD_ID}/shapes", {"data": {"content": content, "shape": shape}, "style": {"fillColor": fill_color, "textColor": text_color, "borderColor": fill_color, "fontSize": "14"}, "position": {"x": x, "y": y, "origin": "center"}, "geometry": {"width": width, "height": height}})

@mcp.tool()
def create_text(content: str, x: float = 0, y: float = 0, font_size: int = 24, color: str = "#1a1a1a") -> dict:
    """Create a text label."""
    return _post(f"/boards/{BOARD_ID}/texts", {"data": {"content": content}, "style": {"color": color, "fontSize": str(font_size), "textAlign": "center"}, "position": {"x": x, "y": y, "origin": "center"}})

@mcp.tool()
def create_frame(title: str, x: float = 0, y: float = 0, width: float = 600, height: float = 400) -> dict:
    """Create a named frame (container) on the board."""
    return _post(f"/boards/{BOARD_ID}/frames", {"data": {"title": title, "format": "custom", "type": "freeform"}, "position": {"x": x, "y": y, "origin": "center"}, "geometry": {"width": width, "height": height}})

@mcp.tool()
def create_connector(start_item_id: str, end_item_id: str, label: str = "", color: str = "#1a1a1a", style: str = "curved") -> dict:
    """Draw an arrow between two items. style: curved, straight, elbowed."""
    body = {"startItem": {"id": start_item_id, "snapTo": "auto"}, "endItem": {"id": end_item_id, "snapTo": "auto"}, "shape": style, "style": {"strokeColor": color, "strokeWidth": "2.0", "endStrokeCap": "stealth", "startStrokeCap": "none"}}
    if label: body["captions"] = [{"content": label, "position": "50%"}]
    return _post(f"/boards/{BOARD_ID}/connectors", body)

@mcp.tool()
def update_item(item_id: str, item_type: str, x: float = None, y: float = None, content: str = None, color: str = None) -> dict:
    """Update position/content/color of an item. item_type: sticky_note, shape, text, frame."""
    body = {}
    if x is not None or y is not None:
        body["position"] = {"origin": "center"}
        if x is not None: body["position"]["x"] = x
        if y is not None: body["position"]["y"] = y
    if content is not None: body["data"] = {"content": content}
    if color is not None: body["style"] = {"fillColor": color}
    ep = {"sticky_note": "sticky_notes", "shape": "shapes", "text": "texts", "frame": "frames"}.get(item_type, item_type + "s")
    return _patch(f"/boards/{BOARD_ID}/{ep}/{item_id}", body)

@mcp.tool()
def delete_item(item_id: str, item_type: str) -> dict:
    """Delete an item. item_type: sticky_note, shape, text, frame."""
    ep = {"sticky_note": "sticky_notes", "shape": "shapes", "text": "texts", "frame": "frames"}.get(item_type, item_type + "s")
    return _delete(f"/boards/{BOARD_ID}/{ep}/{item_id}")

@mcp.tool()
def delete_connector(connector_id: str) -> dict:
    """Delete a connector."""
    return _delete(f"/boards/{BOARD_ID}/connectors/{connector_id}")

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
