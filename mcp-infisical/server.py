"""Infisical Secrets MCP Server - direct HTTP API, no SDK dependency.

Fixes: Uses v3/secrets/batch/raw for create/update/delete to avoid E2EE
cipher requirements on the single-secret v3/secrets/raw endpoint.
Uses httpx.request() for all methods to support json body on DELETE.
"""
import os
import json
import logging
import httpx
from fastmcp import FastMCP

log = logging.getLogger("infisical-mcp")

INFISICAL_URL = os.environ.get("INFISICAL_SITE_URL", "http://infisical:8080")
CLIENT_ID = os.environ.get("INFISICAL_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("INFISICAL_CLIENT_SECRET", "")
WORKSPACE_ID = os.environ.get("INFISICAL_PROJECT_ID", "")
DEFAULT_ENV = os.environ.get("INFISICAL_ENVIRONMENT", "prod")

mcp = FastMCP("infisical", instructions="Manage secrets in Infisical vault")

_token = None
_http = httpx.Client(base_url=INFISICAL_URL, timeout=10)


def _auth():
    global _token
    resp = _http.post("/api/v1/auth/universal-auth/login", json={
        "clientId": CLIENT_ID, "clientSecret": CLIENT_SECRET
    })
    resp.raise_for_status()
    _token = resp.json()["accessToken"]


def _headers():
    global _token
    if not _token:
        _auth()
    return {"Authorization": f"Bearer {_token}"}


def _api(method, path, **kwargs):
    """Make API request. Uses request() to support json body on all HTTP methods."""
    try:
        # Convert json kwarg to content+headers for request() compatibility
        if "json" in kwargs:
            body = json.dumps(kwargs.pop("json"))
            kwargs["content"] = body
            kwargs.setdefault("headers", {})
            kwargs["headers"]["Content-Type"] = "application/json"
        
        # Merge auth headers
        auth_headers = _headers()
        if "headers" in kwargs:
            auth_headers.update(kwargs.pop("headers"))
        
        r = _http.request(method.upper(), path, headers=auth_headers, **kwargs)
        if r.status_code == 401:
            _auth()
            auth_headers = _headers()
            r = _http.request(method.upper(), path, headers=auth_headers, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def list_secrets(folder: str = "/", environment: str = "") -> str:
    """List all secrets in a folder. Shows names with masked values."""
    env = environment or DEFAULT_ENV
    data = _api("get", "/api/v3/secrets/raw", params={
        "workspaceId": WORKSPACE_ID, "environment": env, "secretPath": folder
    })
    if "error" in data:
        return f"Error: {data['error']}"
    secrets = data.get("secrets", [])
    if not secrets:
        return f"No secrets in {folder} ({env})"
    lines = [f"Secrets in {folder} ({env}): {len(secrets)}"]
    for s in secrets:
        val = s.get("secretValue", "")
        masked = val[:4] + "***" if len(val) > 4 else "***"
        lines.append(f"  {s['secretKey']} = {masked}")
    return "\n".join(lines)


@mcp.tool()
async def get_secret(key: str, folder: str = "/", environment: str = "") -> str:
    """Get a specific secret value."""
    env = environment or DEFAULT_ENV
    data = _api("get", f"/api/v3/secrets/raw/{key}", params={
        "workspaceId": WORKSPACE_ID, "environment": env, "secretPath": folder
    })
    if "error" in data:
        return f"Error: {data['error']}"
    s = data.get("secret", {})
    return f"{s.get('secretKey', key)} = {s.get('secretValue', '(empty)')}"


@mcp.tool()
async def create_secret(key: str, value: str, folder: str = "/", environment: str = "") -> str:
    """Create a new secret."""
    env = environment or DEFAULT_ENV
    data = _api("post", "/api/v3/secrets/batch/raw", json={
        "workspaceId": WORKSPACE_ID, "environment": env, "secretPath": folder,
        "secrets": [{"secretKey": key, "secretValue": value}]
    })
    if "error" in data:
        return f"Error: {data['error']}"
    return f"Created {key} in {folder} ({env})"


@mcp.tool()
async def update_secret(key: str, value: str, folder: str = "/", environment: str = "") -> str:
    """Update an existing secret."""
    env = environment or DEFAULT_ENV
    data = _api("patch", "/api/v3/secrets/batch/raw", json={
        "workspaceId": WORKSPACE_ID, "environment": env, "secretPath": folder,
        "secrets": [{"secretKey": key, "secretValue": value}]
    })
    if "error" in data:
        return f"Error: {data['error']}"
    return f"Updated {key} in {folder} ({env})"


@mcp.tool()
async def delete_secret(key: str, folder: str = "/", environment: str = "") -> str:
    """Delete a secret. Use with caution."""
    env = environment or DEFAULT_ENV
    data = _api("delete", "/api/v3/secrets/batch/raw", json={
        "workspaceId": WORKSPACE_ID, "environment": env, "secretPath": folder,
        "secrets": [{"secretKey": key}]
    })
    if "error" in data:
        return f"Error: {data['error']}"
    return f"Deleted {key} from {folder} ({env})"


@mcp.tool()
async def list_folders(parent: str = "/", environment: str = "") -> str:
    """List secret folders."""
    env = environment or DEFAULT_ENV
    data = _api("get", "/api/v1/folders", params={
        "workspaceId": WORKSPACE_ID, "environment": env, "directory": parent
    })
    if "error" in data:
        return f"Error: {data['error']}"
    folders = data.get("folders", [])
    if not folders:
        return f"No folders in {parent}"
    lines = [f"Folders in {parent} ({env}):"]
    for f in folders:
        lines.append(f"  /{f.get('name', '?')}")
    return "\n".join(lines)


@mcp.tool()
async def create_folder(name: str, parent: str = "/", environment: str = "") -> str:
    """Create a new secret folder."""
    env = environment or DEFAULT_ENV
    data = _api("post", "/api/v1/folders", json={
        "workspaceId": WORKSPACE_ID, "environment": env, "directory": parent,
        "name": name
    })
    if "error" in data:
        return f"Error: {data['error']}"
    return f"Created folder /{name} in {parent} ({env})"


@mcp.tool()
async def audit_folders(environment: str = "") -> str:
    """Audit all folders with secret counts."""
    env = environment or DEFAULT_ENV
    fdata = _api("get", "/api/v1/folders", params={
        "workspaceId": WORKSPACE_ID, "environment": env, "directory": "/"
    })
    if "error" in fdata:
        return f"Error: {fdata['error']}"
    folders = fdata.get("folders", [])
    lines = [f"Infisical Audit ({env}):"]
    total = 0
    for f in folders:
        name = f.get("name", "?")
        sdata = _api("get", "/api/v3/secrets/raw", params={
            "workspaceId": WORKSPACE_ID, "environment": env, "secretPath": f"/{name}"
        })
        count = len(sdata.get("secrets", [])) if "error" not in sdata else "err"
        if isinstance(count, int):
            total += count
        lines.append(f"  /{name}: {count} secrets")
    lines.append(f"\nTotal: {len(folders)} folders, {total} secrets")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
