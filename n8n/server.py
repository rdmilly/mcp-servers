#!/usr/bin/env python3
"""n8n MCP Server — n8n workflow automation API as MCP tools.
29 tools: workflows (CRUD, activate/deactivate, import, execute), executions,
credentials, variables, tags, users, webhook trigger.
"""
import os, json
import httpx
from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, Any, List

N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
mcp = FastMCP("n8n")

def _headers(): return {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}

def _req(method, endpoint, data=None):
    url = f"{N8N_URL}/api/v1{endpoint}"
    try:
        with httpx.Client(timeout=30.0) as client:
            fn = getattr(client, method.lower())
            resp = fn(url, headers=_headers(), **(({"json": data} if data else {}) if method != "GET" else {}))
            if resp.status_code >= 400: return {"error": resp.text, "status_code": resp.status_code}
            return resp.json() if resp.text else {"success": True}
    except Exception as e: return {"error": str(e)}

@mcp.tool()
def list_workflows(active: Optional[bool] = None, limit: int = 100) -> str:
    """List all n8n workflows."""
    params = f"?limit={limit}" + (f"&active={str(active).lower()}" if active is not None else "")
    return json.dumps(_req("GET", f"/workflows{params}"), indent=2)

@mcp.tool()
def get_workflow(workflow_id: str) -> str:
    """Get a specific workflow."""
    return json.dumps(_req("GET", f"/workflows/{workflow_id}"), indent=2)

@mcp.tool()
def create_workflow(name: str, nodes: List[Dict], connections: Dict, active: bool = False) -> str:
    """Create a new workflow."""
    return json.dumps(_req("POST", "/workflows", {"name": name, "nodes": nodes, "connections": connections, "active": active, "settings": {"executionOrder": "v1"}}), indent=2)

@mcp.tool()
def update_workflow(workflow_id: str, name: Optional[str] = None, nodes: Optional[List[Dict]] = None, connections: Optional[Dict] = None) -> str:
    """Update an existing workflow."""
    data = {k: v for k, v in {"name": name, "nodes": nodes, "connections": connections}.items() if v is not None}
    return json.dumps(_req("PATCH", f"/workflows/{workflow_id}", data), indent=2)

@mcp.tool()
def delete_workflow(workflow_id: str) -> str:
    """Delete a workflow."""
    return json.dumps(_req("DELETE", f"/workflows/{workflow_id}"), indent=2)

@mcp.tool()
def activate_workflow(workflow_id: str) -> str:
    """Activate a workflow."""
    return json.dumps(_req("POST", f"/workflows/{workflow_id}/activate"), indent=2)

@mcp.tool()
def deactivate_workflow(workflow_id: str) -> str:
    """Deactivate a workflow."""
    return json.dumps(_req("POST", f"/workflows/{workflow_id}/deactivate"), indent=2)

@mcp.tool()
def import_workflow(workflow_json: str) -> str:
    """Import a workflow from JSON string."""
    try: return json.dumps(_req("POST", "/workflows", json.loads(workflow_json)), indent=2)
    except json.JSONDecodeError as e: return json.dumps({"error": f"Invalid JSON: {e}"})

@mcp.tool()
def get_workflow_by_name(name: str) -> str:
    """Find a workflow by name (case-insensitive partial match)."""
    result = _req("GET", "/workflows?limit=100")
    if "error" in result: return json.dumps(result)
    matches = [w for w in result.get("data", []) if name.lower() in w.get("name", "").lower()]
    return json.dumps({"matches": matches, "count": len(matches)}, indent=2)

@mcp.tool()
def execute_workflow_now(workflow_id: str, input_data: Optional[Dict] = None) -> str:
    """Execute a workflow immediately."""
    data = {"workflowData": {"pinData": {"Start": [{"json": input_data}]}}} if input_data else {}
    return json.dumps(_req("POST", f"/workflows/{workflow_id}/run", data or None), indent=2)

@mcp.tool()
def list_executions(workflow_id: Optional[str] = None, status: Optional[str] = None, limit: int = 20) -> str:
    """List executions. status: waiting, running, success, error."""
    params = f"?limit={limit}" + (f"&workflowId={workflow_id}" if workflow_id else "") + (f"&status={status}" if status else "")
    return json.dumps(_req("GET", f"/executions{params}"), indent=2)

@mcp.tool()
def get_execution(execution_id: str, include_data: bool = True) -> str:
    """Get a specific execution."""
    return json.dumps(_req("GET", f"/executions/{execution_id}?includeData={str(include_data).lower()}"), indent=2)

@mcp.tool()
def delete_execution(execution_id: str) -> str:
    """Delete an execution record."""
    return json.dumps(_req("DELETE", f"/executions/{execution_id}"), indent=2)

@mcp.tool()
def retry_execution(execution_id: str) -> str:
    """Retry a failed execution."""
    return json.dumps(_req("POST", f"/executions/{execution_id}/retry"), indent=2)

@mcp.tool()
def list_credentials() -> str:
    """List stored credentials (names/types only)."""
    return json.dumps(_req("GET", "/credentials"), indent=2)

@mcp.tool()
def create_credential(name: str, credential_type: str, data: Dict) -> str:
    """Create a credential."""
    return json.dumps(_req("POST", "/credentials", {"name": name, "type": credential_type, "data": data}), indent=2)

@mcp.tool()
def delete_credential(credential_id: str) -> str:
    """Delete a credential."""
    return json.dumps(_req("DELETE", f"/credentials/{credential_id}"), indent=2)

@mcp.tool()
def list_variables() -> str:
    """List all environment variables."""
    return json.dumps(_req("GET", "/variables"), indent=2)

@mcp.tool()
def create_variable(key: str, value: str) -> str:
    """Create an environment variable."""
    return json.dumps(_req("POST", "/variables", {"key": key, "value": value}), indent=2)

@mcp.tool()
def update_variable(variable_id: str, key: str, value: str) -> str:
    """Update an environment variable."""
    return json.dumps(_req("PATCH", f"/variables/{variable_id}", {"key": key, "value": value}), indent=2)

@mcp.tool()
def delete_variable(variable_id: str) -> str:
    """Delete an environment variable."""
    return json.dumps(_req("DELETE", f"/variables/{variable_id}"), indent=2)

@mcp.tool()
def list_tags() -> str:
    """List all workflow tags."""
    return json.dumps(_req("GET", "/tags"), indent=2)

@mcp.tool()
def create_tag(name: str) -> str:
    """Create a workflow tag."""
    return json.dumps(_req("POST", "/tags", {"name": name}), indent=2)

@mcp.tool()
def update_tag(tag_id: str, name: str) -> str:
    """Update a tag name."""
    return json.dumps(_req("PATCH", f"/tags/{tag_id}", {"name": name}), indent=2)

@mcp.tool()
def delete_tag(tag_id: str) -> str:
    """Delete a tag."""
    return json.dumps(_req("DELETE", f"/tags/{tag_id}"), indent=2)

@mcp.tool()
def list_users() -> str:
    """List all users."""
    return json.dumps(_req("GET", "/users"), indent=2)

@mcp.tool()
def get_current_user() -> str:
    """Get current API user."""
    return json.dumps(_req("GET", "/me"), indent=2)

@mcp.tool()
def trigger_webhook(webhook_path: str, data: Optional[Dict] = None, method: str = "POST") -> str:
    """Trigger a webhook endpoint on n8n."""
    url = f"{N8N_URL}/webhook/{webhook_path}"
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(url) if method.upper() == "GET" else client.post(url, json=data or {})
            try: return json.dumps(resp.json(), indent=2)
            except: return resp.text
    except Exception as e: return json.dumps({"error": str(e)})

@mcp.tool()
def trigger_test_webhook(webhook_path: str, data: Optional[Dict] = None) -> str:
    """Trigger a test webhook (for workflows in test mode)."""
    url = f"{N8N_URL}/webhook-test/{webhook_path}"
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=data or {})
            try: return json.dumps(resp.json(), indent=2)
            except: return resp.text
    except Exception as e: return json.dumps({"error": str(e)})

if __name__ == "__main__": mcp.run(transport="stdio")
