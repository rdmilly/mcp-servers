"""PrintBlocks MCP Server — notation-based code expansion.

Exposes pb_expand, pb_list, health.
Notation -> full project files (server.py, Dockerfile, docker-compose.yml, etc).
"""
import os, json, logging
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP
from notation.parser import parse_notation
from notation.expand import expand, EXPANDERS

SERVICE_NAME = "mcp-printblocks"
PORT = int(os.environ.get("PORT", 9070))
logging.basicConfig(level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")))
log = logging.getLogger(SERVICE_NAME)
mcp = FastMCP(SERVICE_NAME, host="0.0.0.0", port=PORT)


@mcp.tool()
async def pb_expand(notation: str, output: str = "", lang: str = "python") -> dict:
    """Expand PrintBlocks notation into full project files.

    Notation syntax:
      @type name [key=val]    - target: mcp, compose, dockerfile, script, traefik
      +molecule [key=val]     - capability: db-postgres, cache-redis, auth-apikey, db-sqlite, http-client, rate-limit
      def name(args) -> type  - action (indented body = implementation)
      ---                     - file separator

    Example:
      @mcp crm :9061
      +db-postgres
      +cache-redis ttl=300
      def find(q: str) -> list # Search contacts
        return await db.query("SELECT * FROM t WHERE q=$1", [q])
      ---
      @compose crm
      +traefik crm.millyweb.com :9061
      +network millyweb

    Args:
      notation: PrintBlocks notation string
      output:   Output directory path (empty = return without writing)
      lang:     Target language: python (default) | typescript
    """
    try:
        files = expand(notation, output_dir=output, lang=lang)
        result = {"status": "ok", "files_generated": len(files), "files": {}}
        for fname, content in files.items():
            result["files"][fname] = {"size": len(content), "preview": content[:300] + ("..." if len(content) > 300 else "")}
        if output:
            result["output_dir"] = output
            result["message"] = f"Wrote {len(files)} files to {output}"
        return result
    except Exception as e:
        log.error(f"Expansion failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@mcp.tool()
async def pb_list() -> dict:
    """List available PrintBlocks types and molecules."""
    from notation.expanders.mcp_python import MOLECULE_IMPORTS
    return {"types": list(EXPANDERS.keys()), "molecules": list(MOLECULE_IMPORTS.keys())}


@mcp.tool()
async def health() -> dict:
    """Health check."""
    return {"service": SERVICE_NAME, "status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat(), "types": list(EXPANDERS.keys())}


if __name__ == "__main__":
    log.info(f"Starting {SERVICE_NAME} on port {PORT}")
    mcp.run(transport="sse")
