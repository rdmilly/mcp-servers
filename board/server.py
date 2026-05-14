"""mcp-board — MCP server for Cortex Board API.
Tools: board__list_projects, board__get_context, board__get_all_context,
board__get_architecture, board__get_state, board__get_canvas,
board__add_card, board__update_card, board__delete_card,
board__create_project, board__delete_project,
board__add_connection, board__delete_connection,
board__update_position, board__auto_layout
"""
import httpx
from mcp.server.fastmcp import FastMCP

BOARD_BASE = "http://cortex-board:9060"
mcp = FastMCP("board")
client = httpx.Client(base_url=BOARD_BASE, timeout=10)

def _get(path, **params): r = client.get(path, params=params); r.raise_for_status(); return r.json()
def _post(path, json=None, **params): r = client.post(path, json=json or {}, params=params); r.raise_for_status(); return r.json()
def _patch(path, json, **params): r = client.patch(path, json=json, params=params); r.raise_for_status(); return r.json()
def _delete(path, **params): r = client.delete(path, params=params); r.raise_for_status(); return r.json()

@mcp.tool()
def board__list_projects() -> dict:
    """List all project boards."""
    return _get("/api/projects")

@mcp.tool()
def board__create_project(project: str) -> dict:
    """Create a new blank project board."""
    return _post(f"/api/projects/{project}")

@mcp.tool()
def board__delete_project(project: str) -> dict:
    """Delete a project board and all its data."""
    return _delete(f"/api/projects/{project}")

@mcp.tool()
def board__get_context(project: str = "helix") -> dict:
    """Get kanban briefing for session start. project: helix (default)."""
    return _get("/api/context", project=project)

@mcp.tool()
def board__get_all_context() -> dict:
    """Get kanban briefings for ALL projects at once."""
    return _get("/api/context/all")

@mcp.tool()
def board__get_architecture(project: str = "helix") -> dict:
    """Get architecture briefing: components by layer + canvas connections."""
    return _get("/api/context/architecture", project=project)

@mcp.tool()
def board__get_state(project: str = "helix") -> dict:
    """Get raw board state JSON including card IDs."""
    return _get("/api/state", project=project)

@mcp.tool()
def board__get_canvas(project: str = "helix") -> dict:
    """Get canvas data: card positions (x,y) and connections."""
    return _get("/api/canvas", project=project)

@mcp.tool()
def board__add_card(name: str, desc: str = "", layer: str = "other", priority: str = "med", col: str = "idea", file: str = "", notes: str = "", project: str = "helix") -> dict:
    """Add a card. layer: capture|process|store|output|compress|thalamus|infra|user|design|product|other. col: live|fix|p2|p3|idea."""
    return _post("/api/cards", json=dict(name=name, desc=desc, layer=layer, priority=priority, col=col, file=file, notes=notes), project=project)

@mcp.tool()
def board__update_card(card_id: str, name: str = None, desc: str = None, layer: str = None, priority: str = None, col: str = None, file: str = None, notes: str = None, project: str = "helix") -> dict:
    """Partially update a card. Use board__get_state to find card_id."""
    payload = {k: v for k, v in dict(name=name, desc=desc, layer=layer, priority=priority, col=col, file=file, notes=notes).items() if v is not None}
    return _patch(f"/api/cards/{card_id}", json=payload, project=project)

@mcp.tool()
def board__delete_card(card_id: str, project: str = "helix") -> dict:
    """Delete a card."""
    return _delete(f"/api/cards/{card_id}", project=project)

@mcp.tool()
def board__add_connection(from_id: str, to_id: str, label: str = "→", color: str = "#7f77dd", project: str = "helix") -> dict:
    """Draw arrow between two cards. Colors: #7f77dd purple, #E24B4A red, #0F6E56 green, #EF9F27 amber, #185FA5 blue."""
    return _post("/api/canvas/connections", json=dict(from_id=from_id, to_id=to_id, label=label, color=color), project=project)

@mcp.tool()
def board__delete_connection(conn_id: str, project: str = "helix") -> dict:
    """Remove a canvas connection. Use board__get_canvas to find conn_id."""
    return _delete(f"/api/canvas/connections/{conn_id}", project=project)

@mcp.tool()
def board__update_position(card_id: str, x: float, y: float, project: str = "helix") -> dict:
    """Move a card. Canvas 4000x3000px. Typical x: 40-2000, y: 40-1500."""
    return _post("/api/canvas/position", json=dict(card_id=card_id, x=x, y=y), project=project)

@mcp.tool()
def board__auto_layout(project: str = "helix") -> dict:
    """Trigger server-side auto-layout."""
    return _post("/api/canvas/auto-layout", project=project)

if __name__ == "__main__": mcp.run(transport="streamable-http")
