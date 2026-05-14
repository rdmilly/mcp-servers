"""Millyweb Infrastructure Knowledge Base MCP Gateway.

Provides searchable, writable access to the Millyweb infrastructure KB.
Registered as Gateway #25 in ContextForge.
"""

import os
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# Configuration
KB_ROOT = Path(os.environ.get("KB_ROOT", "/data/kb"))
GIT_COMMIT = os.environ.get("GIT_AUTO_COMMIT", "true").lower() == "true"

mcp = FastMCP("kb_mcp", host="0.0.0.0", port=8000)


# ─── Input Models ───────────────────────────────────────────

class KBSearchInput(BaseModel):
    """Search the infrastructure knowledge base."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search terms (e.g. 'traefik routes', 'port 8090', 'mcp-front oauth', 'VPS1 disk')",
        min_length=1,
        max_length=200,
    )
    max_results: int = Field(
        default=10,
        description="Maximum matching sections to return",
        ge=1,
        le=50,
    )


class KBReadInput(BaseModel):
    """Read a specific KB document."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(
        ...,
        description=(
            "Relative path within KB. Examples: README.md, "
            "infrastructure/vps2-workloads.md, mcp/architecture.md, "
            "domains/millyweb.com.md, services/all-services.md"
        ),
        min_length=1,
        max_length=200,
    )


class KBUpdateInput(BaseModel):
    """Update or create a KB document."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(
        ...,
        description="Relative file path within KB (e.g. 'infrastructure/vps2-workloads.md')",
        min_length=1,
        max_length=200,
    )
    content: str = Field(
        ...,
        description="Full markdown content to write",
        min_length=1,
    )
    commit_message: str = Field(
        default="KB update via Claude",
        description="Git commit message describing the change",
        max_length=200,
    )


# ─── Helpers ────────────────────────────────────────────────

def _safe_path(relative: str) -> Path:
    """Resolve a relative path safely within KB_ROOT."""
    resolved = (KB_ROOT / relative).resolve()
    if not str(resolved).startswith(str(KB_ROOT.resolve())):
        raise ValueError(f"Path traversal blocked: {relative}")
    return resolved


def _git_commit(message: str) -> Optional[str]:
    """Auto-commit changes in the KB repo."""
    if not GIT_COMMIT:
        return None
    try:
        subprocess.run(["git", "add", "-A"], cwd=KB_ROOT, capture_output=True, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", message, "--allow-empty"],
            cwd=KB_ROOT, capture_output=True, text=True, check=True,
        )
        # Extract commit hash
        for line in result.stdout.splitlines():
            if line.strip().startswith("["):
                parts = line.split()
                for p in parts:
                    if len(p) >= 7 and p.replace("]", "").isalnum():
                        return p.replace("]", "")
        return "committed"
    except subprocess.CalledProcessError:
        return None


def _search_file(filepath: Path, terms: List[str]) -> List[dict]:
    """Search a single markdown file for matching sections."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    matches = []
    lines = text.splitlines()
    current_section = "(top)"
    section_start = 0

    for i, line in enumerate(lines):
        if line.startswith("#"):
            current_section = line.lstrip("# ").strip()
            section_start = i

    # Search by section blocks
    sections = []
    current_heading = "(top)"
    current_lines = []
    start_line = 0

    for i, line in enumerate(lines):
        if line.startswith("#") and current_lines:
            sections.append((current_heading, start_line, current_lines))
            current_heading = line.lstrip("# ").strip()
            current_lines = []
            start_line = i
        current_lines.append(line)
    if current_lines:
        sections.append((current_heading, start_line, current_lines))

    rel_path = str(filepath.relative_to(KB_ROOT))

    for heading, start, section_lines in sections:
        section_text = "\n".join(section_lines).lower()
        score = sum(1 for t in terms if t.lower() in section_text)
        if score > 0:
            # Return the section with context
            content = "\n".join(section_lines[:30])  # Cap at 30 lines per section
            if len(section_lines) > 30:
                content += f"\n... ({len(section_lines) - 30} more lines)"
            matches.append({
                "file": rel_path,
                "section": heading,
                "line": start + 1,
                "score": score,
                "content": content,
            })

    return matches


# ─── Tools ──────────────────────────────────────────────────

@mcp.tool(
    name="kb_search",
    annotations={
        "title": "Search Infrastructure KB",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def kb_search(params: KBSearchInput) -> str:
    """Search Millyweb infrastructure knowledge base — servers, containers,
    ports, domains, MCP architecture, networking, services, Traefik routes,
    Docker configs, credentials, VPS details, WireGuard, monitoring.
    Returns matching sections with file context."""

    terms = params.query.split()
    all_matches = []

    for md_file in KB_ROOT.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        all_matches.extend(_search_file(md_file, terms))

    # Sort by relevance score descending
    all_matches.sort(key=lambda m: m["score"], reverse=True)
    results = all_matches[: params.max_results]

    if not results:
        return json.dumps({
            "query": params.query,
            "results": [],
            "message": "No matches found. Try broader terms or use kb_list to see available docs.",
        }, indent=2)

    return json.dumps({
        "query": params.query,
        "total_matches": len(all_matches),
        "showing": len(results),
        "results": results,
    }, indent=2)


@mcp.tool(
    name="kb_read",
    annotations={
        "title": "Read KB Document",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def kb_read(params: KBReadInput) -> str:
    """Read a Millyweb KB document by path. Use kb_list to see available docs.
    Contains: server specs, container inventories, port allocations, domain maps,
    MCP pipeline details, Traefik routes, network topology, service configs."""

    filepath = _safe_path(params.path)
    if not filepath.exists():
        available = [str(f.relative_to(KB_ROOT)) for f in KB_ROOT.rglob("*.md") if ".git" not in f.parts]
        return json.dumps({
            "error": f"File not found: {params.path}",
            "available": sorted(available),
        }, indent=2)

    content = filepath.read_text(encoding="utf-8")
    stat = filepath.stat()

    return json.dumps({
        "path": params.path,
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "content": content,
    }, indent=2)


@mcp.tool(
    name="kb_update",
    annotations={
        "title": "Update KB Document",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def kb_update(params: KBUpdateInput) -> str:
    """Update or create a Millyweb KB document. Use after deploying new services,
    changing infrastructure, or when information becomes stale. Changes are
    git-committed automatically."""

    filepath = _safe_path(params.path)

    # Create parent directories if needed
    filepath.parent.mkdir(parents=True, exist_ok=True)

    existed = filepath.exists()
    filepath.write_text(params.content, encoding="utf-8")

    commit_hash = _git_commit(params.commit_message)

    return json.dumps({
        "status": "updated" if existed else "created",
        "path": params.path,
        "size_bytes": filepath.stat().st_size,
        "git_commit": commit_hash,
        "message": params.commit_message,
    }, indent=2)


@mcp.tool(
    name="kb_list",
    annotations={
        "title": "List KB Documents",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def kb_list() -> str:
    """List all documents in the Millyweb infrastructure knowledge base
    with file sizes and last-modified dates. Use to discover what information
    is available about servers, containers, domains, MCP, networking."""

    docs = []
    for md_file in sorted(KB_ROOT.rglob("*.md")):
        if ".git" in md_file.parts:
            continue
        stat = md_file.stat()
        docs.append({
            "path": str(md_file.relative_to(KB_ROOT)),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    return json.dumps({
        "kb_root": str(KB_ROOT),
        "total_files": len(docs),
        "total_size_bytes": sum(d["size_bytes"] for d in docs),
        "documents": docs,
    }, indent=2)


if __name__ == "__main__":
    mcp.run(transport="sse")
