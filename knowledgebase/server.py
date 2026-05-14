"""Millyweb Infrastructure Knowledge Base MCP Gateway."""
import os, re, json, subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

KB_ROOT = Path(os.environ.get("KB_ROOT", "/data/kb"))
GIT_COMMIT = os.environ.get("GIT_AUTO_COMMIT", "true").lower() == "true"
mcp = FastMCP("kb_mcp", host="0.0.0.0", port=8000)

class KBSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., min_length=1, max_length=200)
    max_results: int = Field(default=10, ge=1, le=50)

class KBReadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(..., min_length=1, max_length=200)

class KBUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    commit_message: str = Field(default="KB update via Claude", max_length=200)

def _safe_path(relative):
    resolved = (KB_ROOT / relative).resolve()
    if not str(resolved).startswith(str(KB_ROOT.resolve())): raise ValueError(f"Path traversal blocked: {relative}")
    return resolved

def _git_commit(message):
    if not GIT_COMMIT: return None
    try:
        subprocess.run(["git", "add", "-A"], cwd=KB_ROOT, capture_output=True, check=True)
        result = subprocess.run(["git", "commit", "-m", message, "--allow-empty"], cwd=KB_ROOT, capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if line.strip().startswith("["):
                for p in line.split():
                    if len(p) >= 7 and p.replace("]", "").isalnum(): return p.replace("]", "")
        return "committed"
    except subprocess.CalledProcessError: return None

def _search_file(filepath, terms):
    try: text = filepath.read_text(encoding="utf-8")
    except Exception: return []
    sections, current_heading, current_lines, start_line = [], "(top)", [], 0
    for i, line in enumerate(text.splitlines()):
        if line.startswith("#") and current_lines:
            sections.append((current_heading, start_line, current_lines))
            current_heading, current_lines, start_line = line.lstrip("# ").strip(), [], i
        current_lines.append(line)
    if current_lines: sections.append((current_heading, start_line, current_lines))
    rel_path, matches = str(filepath.relative_to(KB_ROOT)), []
    for heading, start, section_lines in sections:
        score = sum(1 for t in terms if t.lower() in "\n".join(section_lines).lower())
        if score > 0:
            content = "\n".join(section_lines[:30])
            if len(section_lines) > 30: content += f"\n... ({len(section_lines)-30} more lines)"
            matches.append({"file": rel_path, "section": heading, "line": start+1, "score": score, "content": content})
    return matches

@mcp.tool(name="kb_search", annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def kb_search(params: KBSearchInput) -> str:
    """Search Millyweb infrastructure KB — servers, containers, ports, domains, MCP, networking, Traefik, Docker."""
    terms, all_matches = params.query.split(), []
    for md_file in KB_ROOT.rglob("*.md"):
        if ".git" not in md_file.parts: all_matches.extend(_search_file(md_file, terms))
    all_matches.sort(key=lambda m: m["score"], reverse=True)
    results = all_matches[:params.max_results]
    if not results: return json.dumps({"query": params.query, "results": [], "message": "No matches. Try broader terms or kb_list."}, indent=2)
    return json.dumps({"query": params.query, "total_matches": len(all_matches), "showing": len(results), "results": results}, indent=2)

@mcp.tool(name="kb_read", annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def kb_read(params: KBReadInput) -> str:
    """Read a KB document. Use kb_list to discover available docs."""
    filepath = _safe_path(params.path)
    if not filepath.exists():
        available = sorted(str(f.relative_to(KB_ROOT)) for f in KB_ROOT.rglob("*.md") if ".git" not in f.parts)
        return json.dumps({"error": f"Not found: {params.path}", "available": available}, indent=2)
    stat = filepath.stat()
    return json.dumps({"path": params.path, "size_bytes": stat.st_size, "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(), "content": filepath.read_text(encoding="utf-8")}, indent=2)

@mcp.tool(name="kb_update", annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True})
async def kb_update(params: KBUpdateInput) -> str:
    """Update or create a KB document. Auto-committed to git."""
    filepath = _safe_path(params.path)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    existed = filepath.exists()
    filepath.write_text(params.content, encoding="utf-8")
    return json.dumps({"status": "updated" if existed else "created", "path": params.path, "size_bytes": filepath.stat().st_size, "git_commit": _git_commit(params.commit_message), "message": params.commit_message}, indent=2)

@mcp.tool(name="kb_list", annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def kb_list() -> str:
    """List all documents in the infrastructure KB."""
    docs = [{"path": str(f.relative_to(KB_ROOT)), "size_bytes": f.stat().st_size, "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()} for f in sorted(KB_ROOT.rglob("*.md")) if ".git" not in f.parts]
    return json.dumps({"kb_root": str(KB_ROOT), "total_files": len(docs), "total_size_bytes": sum(d["size_bytes"] for d in docs), "documents": docs}, indent=2)

if __name__ == "__main__": mcp.run(transport="sse")
