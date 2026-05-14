"""Millyweb Working Documents KB — MCP Gateway.

Provides searchable, writable access to working documents:
project PRDs, research, journals, changelogs, business docs, content plans.
Separate from the Infrastructure KB to keep reference docs clean.
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
KB_ROOT = Path(os.environ.get("KB_ROOT", "/data/workdocs"))
GIT_COMMIT = os.environ.get("GIT_AUTO_COMMIT", "true").lower() == "true"

mcp = FastMCP("workdocs_mcp", host="0.0.0.0", port=8000)


# --- Input Models ---

class SearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., description="Search terms (e.g. 'oculus anubis', 'context engine prd', 'working journal feb')", min_length=1, max_length=200)
    max_results: int = Field(default=10, description="Maximum matching sections to return", ge=1, le=50)


class ReadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(..., description="Relative path within working docs (e.g. 'projects/contextengine/prd.md', 'journals/2026-02-12.md')", min_length=1, max_length=200)


class UpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(..., description="Relative file path (e.g. 'journals/2026-02-12.md')", min_length=1, max_length=200)
    content: str = Field(..., description="Full markdown content to write", min_length=1)
    commit_message: str = Field(default="Working docs update via Claude", description="Git commit message", max_length=200)




class AppendInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(..., description="Relative file path to append to", min_length=1, max_length=200)
    content: str = Field(..., description="Markdown content to append (added after a blank line)", min_length=1)
    commit_message: str = Field(default="Working docs append via Claude", description="Git commit message", max_length=200)

# --- Helpers ---

def _safe_path(relative: str) -> Path:
    resolved = (KB_ROOT / relative).resolve()
    if not str(resolved).startswith(str(KB_ROOT.resolve())):
        raise ValueError(f"Path traversal blocked: {relative}")
    return resolved


def _git_commit(message: str) -> Optional[str]:
    if not GIT_COMMIT:
        return None
    try:
        subprocess.run(["git", "add", "-A"], cwd=KB_ROOT, capture_output=True, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", message, "--allow-empty"],
            cwd=KB_ROOT, capture_output=True, text=True, check=True,
        )
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
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    sections = []
    current_heading = "(top)"
    current_lines = []
    start_line = 0

    lines = text.splitlines()
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
    matches = []

    for heading, start, section_lines in sections:
        section_text = "\n".join(section_lines).lower()
        score = sum(1 for t in terms if t.lower() in section_text)
        if score > 0:
            content = "\n".join(section_lines[:30])
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


# --- Tools ---

@mcp.tool(
    name="workdocs_search",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def workdocs_search(params: SearchInput) -> str:
    """Search working documents — project PRDs, research notes, journals,
    changelogs, business docs, content plans, specs, Oculus Anubis investigation,
    MW Development materials, social media content. Returns matching sections."""

    terms = params.query.split()
    all_matches = []

    for md_file in KB_ROOT.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        all_matches.extend(_search_file(md_file, terms))

    all_matches.sort(key=lambda m: m["score"], reverse=True)
    results = all_matches[:params.max_results]

    if not results:
        return json.dumps({
            "query": params.query,
            "results": [],
            "message": "No matches found. Try broader terms or use workdocs_list to see available docs.",
        }, indent=2)

    return json.dumps({
        "query": params.query,
        "total_matches": len(all_matches),
        "showing": len(results),
        "results": results,
    }, indent=2)


@mcp.tool(
    name="workdocs_read",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def workdocs_read(params: ReadInput) -> str:
    """Read a working document by path. Contains: project PRDs, session journals,
    server changelogs, Oculus research, MW Development plans, social content,
    specs, business documents. Use workdocs_list to discover available files."""

    filepath = _safe_path(params.path)
    if not filepath.exists():
        available = [str(f.relative_to(KB_ROOT)) for f in KB_ROOT.rglob("*.md") if ".git" not in f.parts]
        return json.dumps({"error": f"File not found: {params.path}", "available": sorted(available)}, indent=2)

    content = filepath.read_text(encoding="utf-8")
    stat = filepath.stat()

    return json.dumps({
        "path": params.path,
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "content": content,
    }, indent=2)


@mcp.tool(
    name="workdocs_update",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def workdocs_update(params: UpdateInput) -> str:
    """Create or update a working document. Use for: saving session journals,
    updating changelogs, writing PRDs, storing research notes, creating content
    plans. Changes are git-committed automatically."""

    filepath = _safe_path(params.path)
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
    name="workdocs_list",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def workdocs_list() -> str:
    """List all working documents — project PRDs, journals, changelogs,
    research, business docs, content plans, specs. Shows file paths,
    sizes, and last-modified dates."""

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




@mcp.tool(
    name="workdocs_append",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def workdocs_append(params: AppendInput) -> str:
    """Append content to an existing working document without overwriting it.
    Use for: adding new sections to PRDs, appending journal entries, adding
    changelog items. Creates the file if it does not exist."""

    filepath = _safe_path(params.path)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    existing = filepath.read_text(encoding="utf-8") if filepath.exists() else ""
    separator = "\n\n" if existing and not existing.endswith("\n\n") else ("\n" if existing and not existing.endswith("\n") else "")
    filepath.write_text(existing + separator + params.content, encoding="utf-8")
    commit_hash = _git_commit(params.commit_message)

    return json.dumps({
        "status": "appended",
        "path": params.path,
        "size_bytes": filepath.stat().st_size,
        "appended_bytes": len(params.content.encode()),
        "git_commit": commit_hash,
        "message": params.commit_message,
    }, indent=2)

if __name__ == "__main__":
    mcp.run(transport="sse")
