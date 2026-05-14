"""Loki MCP Server — LogQL query interface for Grafana Loki.
6 tools: loki_config, loki_labels, loki_query, loki_ready, loki_series, loki_stats
Reconstructed from provisioner manifest (image not cached locally).
"""
import os, json
from typing import Optional
import httpx
from mcp.server.fastmcp import FastMCP

LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100")
mcp = FastMCP("loki")

async def _get(path: str, **params):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{LOKI_URL}{path}", params=params or None)
        r.raise_for_status()
        return r.json()

async def _get_text(path: str):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{LOKI_URL}{path}")
        r.raise_for_status()
        return r.text

@mcp.tool()
async def loki_config() -> dict:
    """Get Loki server configuration (YAML format)."""
    config = await _get_text("/config")
    return {"config": config}

@mcp.tool()
async def loki_labels(name: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> dict:
    """Get label names or values from Loki. Without 'name' returns all label names; with 'name' returns values for that label."""
    params = {}
    if start: params["start"] = start
    if end: params["end"] = end
    if name:
        data = await _get(f"/loki/api/v1/label/{name}/values", **params)
        return {"type": "values", "count": len(data.get("data", [])), "labels": data.get("data", [])}
    data = await _get("/loki/api/v1/labels", **params)
    return {"type": "names", "count": len(data.get("data", [])), "labels": data.get("data", [])}

@mcp.tool()
async def loki_query(query: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 100, direction: str = "backward") -> dict:
    """Execute a LogQL query. query: LogQL string e.g. {app=\"nginx\"}. start/end: RFC3339 or relative like 1h."""
    params = {"query": query, "limit": limit, "direction": direction}
    if start: params["start"] = start
    if end: params["end"] = end
    data = await _get("/loki/api/v1/query_range", **params)
    results = data.get("data", {}).get("result", [])
    lines = []
    for stream in results:
        labels = stream.get("stream", {})
        for ts, msg in stream.get("values", []):
            lines.append(f"[{ts}] {msg}")
    output = "\n".join(lines[-limit:]) if lines else "(no results)"
    return {"resultType": data.get("data", {}).get("resultType", "streams"), "count": len(lines), "output": output}

@mcp.tool()
async def loki_ready() -> dict:
    """Check if Loki is ready to accept requests."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{LOKI_URL}/ready")
            ready = r.status_code == 200
            return {"ready": ready, "message": r.text.strip()}
    except Exception as e:
        return {"ready": False, "message": str(e)}

@mcp.tool()
async def loki_series(match: list, start: Optional[str] = None, end: Optional[str] = None) -> dict:
    """Get log streams matching label selectors. match: list of selectors e.g. ['{app=nginx}']."""
    params = {"match[]": match}
    if start: params["start"] = start
    if end: params["end"] = end
    data = await _get("/loki/api/v1/series", **params)
    series = data.get("data", [])
    output = "\n".join(json.dumps(s) for s in series)
    return {"count": len(series), "series": series, "output": output}

@mcp.tool()
async def loki_stats(query: str, start: Optional[str] = None, end: Optional[str] = None) -> dict:
    """Get index statistics for a LogQL selector. query: e.g. {app=nginx}."""
    params = {"query": query}
    if start: params["start"] = start
    if end: params["end"] = end
    data = await _get("/loki/api/v1/index/stats", **params)
    stats = data.get("data", {})
    output = json.dumps(stats, indent=2)
    return {
        "streams": stats.get("streams", 0),
        "chunks": stats.get("chunks", 0),
        "bytes": stats.get("bytes", 0),
        "entries": stats.get("entries", 0),
        "output": output,
    }

if __name__ == "__main__": mcp.run(transport="sse")
