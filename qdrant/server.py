"""Qdrant MCP Server — vector memory store.
2 tools: qdrant-find, qdrant-store
Connects to Qdrant at QDRANT_URL with COLLECTION_NAME.
Reconstructed from provisioner manifest (image not cached locally).
"""
import os, json
from typing import Optional, Dict
import httpx
from mcp.server.fastmcp import FastMCP
try:
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer(os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    def _embed(text: str): return _model.encode(text).tolist()
except ImportError:
    import hashlib
    def _embed(text: str): return [float(int(c, 16)) / 255.0 for c in hashlib.sha256(text.encode()).hexdigest()[:384]]

QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.environ.get("COLLECTION_NAME", "mcp-memory")
mcp = FastMCP("qdrant")

async def _search(vector: list, limit: int = 5):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
                         json={"vector": vector, "limit": limit, "with_payload": True})
        r.raise_for_status()
        return r.json().get("result", [])

async def _upsert(point_id: str, vector: list, payload: dict):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"{QDRANT_URL}/collections/{COLLECTION}/points",
                        json={"points": [{"id": point_id, "vector": vector, "payload": payload}]})
        r.raise_for_status()
        return r.json()

@mcp.tool(name="qdrant-find")
async def qdrant_find(query: str) -> str:
    """Look up memories in Qdrant by semantic similarity."""
    import uuid
    vector = _embed(query)
    results = await _search(vector)
    if not results: return "No memories found."
    lines = []
    for r in results:
        payload = r.get("payload", {})
        score = r.get("score", 0)
        info = payload.get("information", payload.get("text", json.dumps(payload)))
        lines.append(f"[{score:.3f}] {info}")
    return "\n".join(lines)

@mcp.tool(name="qdrant-store")
async def qdrant_store(information: str, metadata: Optional[Dict] = None) -> str:
    """Store information in Qdrant memory for later retrieval."""
    import uuid, time
    point_id = str(uuid.uuid4())
    vector = _embed(information)
    payload = {"information": information, "timestamp": time.time()}
    if metadata: payload.update(metadata)
    await _upsert(point_id, vector, payload)
    return f"Stored memory (id: {point_id})"

if __name__ == "__main__": mcp.run(transport="sse")
