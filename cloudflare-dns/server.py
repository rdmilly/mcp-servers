"""MCP Cloudflare DNS & Zone Management Server.
FastMCP — DNS records, zones, SSL, cache, firewall, page rules, analytics.
"""
import os
from typing import Optional
import httpx
from fastmcp import FastMCP

CF_API = "https://api.cloudflare.com/client/v4"
CF_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
mcp = FastMCP("Cloudflare DNS & Zone Management", host="0.0.0.0", port=9038)

def _h(): return {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}
async def _get(p, params=None):
    async with httpx.AsyncClient(timeout=30) as c: r = await c.get(f"{CF_API}{p}", headers=_h(), params=params); return r.json()
async def _post(p, data):
    async with httpx.AsyncClient(timeout=30) as c: r = await c.post(f"{CF_API}{p}", headers=_h(), json=data); return r.json()
async def _put(p, data):
    async with httpx.AsyncClient(timeout=30) as c: r = await c.put(f"{CF_API}{p}", headers=_h(), json=data); return r.json()
async def _patch(p, data):
    async with httpx.AsyncClient(timeout=30) as c: r = await c.patch(f"{CF_API}{p}", headers=_h(), json=data); return r.json()
async def _delete(p):
    async with httpx.AsyncClient(timeout=30) as c: r = await c.delete(f"{CF_API}{p}", headers=_h()); return r.json()

def _fmt(resp):
    import json
    if resp.get("success"):
        result = resp.get("result")
        return json.dumps(result, indent=2, default=str) if isinstance(result, (list, dict)) else str(result)
    return f"ERROR: {json.dumps(resp.get('errors', []), indent=2)}"

@mcp.tool()
async def zones_list() -> str:
    """List all Cloudflare zones."""
    resp = await _get("/zones", {"per_page": 50})
    if resp.get("success"): return "\n".join(f"{z['id']}  {z['name']}  status={z['status']}  plan={z.get('plan',{}).get('name','?')}" for z in resp["result"]) or "No zones"
    return _fmt(resp)

@mcp.tool()
async def zone_get(zone_id: str) -> str:
    """Get detailed info about a zone."""
    return _fmt(await _get(f"/zones/{zone_id}"))

@mcp.tool()
async def dns_list(zone_id: str, record_type: Optional[str] = None, name: Optional[str] = None) -> str:
    """List DNS records. Optionally filter by type (A, CNAME, MX, TXT, etc) and/or name."""
    params = {"per_page": 100}
    if record_type: params["type"] = record_type.upper()
    if name: params["name"] = name
    resp = await _get(f"/zones/{zone_id}/dns_records", params)
    if resp.get("success"): return "\n".join(f"{r['id']}  {r['type']:6} {r['name']:40} -> {r['content']:30} TTL={r.get('ttl','auto')} {'proxied' if r.get('proxied') else 'dns-only'}" for r in resp["result"]) or "No records"
    return _fmt(resp)

@mcp.tool()
async def dns_create(zone_id: str, record_type: str, name: str, content: str, proxied: bool = True, ttl: int = 1, priority: Optional[int] = None) -> str:
    """Create a DNS record. type: A, AAAA, CNAME, MX, TXT, etc. TTL=1 = auto."""
    data = {"type": record_type.upper(), "name": name, "content": content, "proxied": proxied, "ttl": ttl}
    if priority is not None: data["priority"] = priority
    return _fmt(await _post(f"/zones/{zone_id}/dns_records", data))

@mcp.tool()
async def dns_update(zone_id: str, record_id: str, record_type: Optional[str] = None, name: Optional[str] = None, content: Optional[str] = None, proxied: Optional[bool] = None, ttl: Optional[int] = None) -> str:
    """Update an existing DNS record. Only provide fields to change."""
    cur = await _get(f"/zones/{zone_id}/dns_records/{record_id}")
    if not cur.get("success"): return _fmt(cur)
    rec = cur["result"]
    data = {"type": (record_type or rec["type"]).upper(), "name": name or rec["name"], "content": content or rec["content"], "proxied": proxied if proxied is not None else rec.get("proxied", False), "ttl": ttl or rec.get("ttl", 1)}
    return _fmt(await _put(f"/zones/{zone_id}/dns_records/{record_id}", data))

@mcp.tool()
async def dns_delete(zone_id: str, record_id: str) -> str:
    """Delete a DNS record."""
    resp = await _delete(f"/zones/{zone_id}/dns_records/{record_id}")
    return f"Deleted {record_id}" if resp.get("success") else _fmt(resp)

@mcp.tool()
async def dns_export(zone_id: str) -> str:
    """Export DNS records in BIND format."""
    async with httpx.AsyncClient(timeout=30) as c: r = await c.get(f"{CF_API}/zones/{zone_id}/dns_records/export", headers=_h()); return r.text

@mcp.tool()
async def ssl_get(zone_id: str) -> str:
    """Get SSL/TLS mode (off, flexible, full, strict)."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/ssl"))

@mcp.tool()
async def ssl_set(zone_id: str, value: str) -> str:
    """Set SSL/TLS mode: off, flexible, full, strict."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/ssl", {"value": value}))

@mcp.tool()
async def always_https_get(zone_id: str) -> str:
    """Check if Always Use HTTPS is enabled."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/always_use_https"))

@mcp.tool()
async def always_https_set(zone_id: str, value: str) -> str:
    """Enable/disable Always Use HTTPS. value: on or off."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/always_use_https", {"value": value}))

@mcp.tool()
async def cache_purge_all(zone_id: str) -> str:
    """Purge ALL cache for a zone."""
    return _fmt(await _post(f"/zones/{zone_id}/purge_cache", {"purge_everything": True}))

@mcp.tool()
async def cache_purge_urls(zone_id: str, urls: list[str]) -> str:
    """Purge specific URLs from cache."""
    return _fmt(await _post(f"/zones/{zone_id}/purge_cache", {"files": urls}))

@mcp.tool()
async def cache_level_get(zone_id: str) -> str:
    """Get cache level (aggressive, basic, simplified)."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/cache_level"))

@mcp.tool()
async def cache_level_set(zone_id: str, value: str) -> str:
    """Set cache level: aggressive, basic, simplified."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/cache_level", {"value": value}))

@mcp.tool()
async def dev_mode_get(zone_id: str) -> str:
    """Check if Development Mode is on (bypasses cache)."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/development_mode"))

@mcp.tool()
async def dev_mode_set(zone_id: str, value: str) -> str:
    """Toggle Dev Mode: on or off."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/development_mode", {"value": value}))

@mcp.tool()
async def security_level_get(zone_id: str) -> str:
    """Get security level."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/security_level"))

@mcp.tool()
async def security_level_set(zone_id: str, value: str) -> str:
    """Set security level: off, essentially_off, low, medium, high, under_attack."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/security_level", {"value": value}))

@mcp.tool()
async def waf_rules_list(zone_id: str) -> str:
    """List WAF custom firewall rules."""
    return _fmt(await _get(f"/zones/{zone_id}/firewall/rules", {"per_page": 100}))

@mcp.tool()
async def ip_access_rules_list(zone_id: str) -> str:
    """List IP access rules (allowlist/blocklist)."""
    return _fmt(await _get(f"/zones/{zone_id}/firewall/access_rules/rules", {"per_page": 100}))

@mcp.tool()
async def ip_access_rule_create(zone_id: str, target: str, value: str, mode: str = "block", notes: str = "") -> str:
    """Create IP access rule. target: ip/ip_range/country. mode: block, challenge, whitelist."""
    return _fmt(await _post(f"/zones/{zone_id}/firewall/access_rules/rules", {"mode": mode, "configuration": {"target": target, "value": value}, "notes": notes}))

@mcp.tool()
async def page_rules_list(zone_id: str) -> str:
    """List all page rules."""
    return _fmt(await _get(f"/zones/{zone_id}/pagerules"))

@mcp.tool()
async def page_rule_create(zone_id: str, url_pattern: str, actions: list[dict], priority: int = 1, status: str = "active") -> str:
    """Create a page rule. actions: [{id, value}]. Example: [{id: forwarding_url, value: {url, status_code: 301}}]"""
    return _fmt(await _post(f"/zones/{zone_id}/pagerules", {"targets": [{"target": "url", "constraint": {"operator": "matches", "value": url_pattern}}], "actions": actions, "priority": priority, "status": status}))

@mcp.tool()
async def redirect_rules_list(zone_id: str) -> str:
    """List redirect rules (Single Redirects) for a zone."""
    return _fmt(await _get(f"/zones/{zone_id}/rulesets", {"phase": "http_request_dynamic_redirect"}))

@mcp.tool()
async def zone_settings_list(zone_id: str) -> str:
    """List all zone settings."""
    import json
    resp = await _get(f"/zones/{zone_id}/settings")
    if resp.get("success"): return "\n".join(sorted(f"{s['id']:30} = {json.dumps(s.get('value','')) if isinstance(s.get('value'), dict) else s.get('value','')}" for s in resp["result"]))
    return _fmt(resp)

@mcp.tool()
async def zone_setting_set(zone_id: str, setting_id: str, value: str) -> str:
    """Update a zone setting. Use zone_settings_list to see available settings."""
    import json
    try: parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError): parsed = value
    return _fmt(await _patch(f"/zones/{zone_id}/settings/{setting_id}", {"value": parsed}))

@mcp.tool()
async def zone_analytics(zone_id: str, since: Optional[str] = None, until: Optional[str] = None) -> str:
    """Get zone analytics. since/until: ISO or relative (-1440 = last 24h)."""
    params = {}
    if since: params["since"] = since
    if until: params["until"] = until
    return _fmt(await _get(f"/zones/{zone_id}/analytics/dashboard", params))

@mcp.tool()
async def cf_health() -> str:
    """Verify Cloudflare API connectivity."""
    resp = await _get("/zones", {"per_page": 50})
    if resp.get("success"): zones = resp["result"]; return f"Connected. {len(zones)} zones: {', '.join(z['name'] for z in zones)}"
    return _fmt(resp)

if __name__ == "__main__": mcp.run(transport="streamable-http")
