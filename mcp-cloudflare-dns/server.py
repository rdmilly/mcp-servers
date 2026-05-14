"""MCP Cloudflare DNS & Zone Management Server
FastMCP server for Cloudflare API v4 — DNS records, zones, SSL, cache, firewall, redirects.
"""
import os
import httpx
from fastmcp import FastMCP
from typing import Optional

CF_API = "https://api.cloudflare.com/client/v4"
CF_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")

mcp = FastMCP(
    "Cloudflare DNS & Zone Management",
    host="0.0.0.0",
    port=9038,
)

def _headers():
    return {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}

async def _get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{CF_API}{path}", headers=_headers(), params=params)
        return r.json()

async def _post(path: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{CF_API}{path}", headers=_headers(), json=data)
        return r.json()

async def _put(path: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"{CF_API}{path}", headers=_headers(), json=data)
        return r.json()

async def _patch(path: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.patch(f"{CF_API}{path}", headers=_headers(), json=data)
        return r.json()

async def _delete(path: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.delete(f"{CF_API}{path}", headers=_headers())
        return r.json()

def _fmt(resp: dict) -> str:
    """Format API response concisely."""
    import json
    if resp.get("success"):
        result = resp.get("result")
        if isinstance(result, list):
            return json.dumps(result, indent=2, default=str)
        elif isinstance(result, dict):
            return json.dumps(result, indent=2, default=str)
        return str(result)
    errors = resp.get("errors", [])
    return f"ERROR: {json.dumps(errors, indent=2)}"


# ── ZONES ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def zones_list() -> str:
    """List all Cloudflare zones (domains) in the account."""
    resp = await _get("/zones", {"per_page": 50})
    if resp.get("success"):
        zones = resp["result"]
        lines = []
        for z in zones:
            lines.append(f"{z['id']}  {z['name']}  status={z['status']}  plan={z.get('plan',{}).get('name','?')}")
        return "\n".join(lines) if lines else "No zones found"
    return _fmt(resp)

@mcp.tool()
async def zone_get(zone_id: str) -> str:
    """Get detailed info about a specific zone by its ID."""
    return _fmt(await _get(f"/zones/{zone_id}"))


# ── DNS RECORDS ──────────────────────────────────────────────────────────────

@mcp.tool()
async def dns_list(
    zone_id: str,
    record_type: Optional[str] = None,
    name: Optional[str] = None,
) -> str:
    """List DNS records for a zone. Optionally filter by type (A, AAAA, CNAME, MX, TXT, etc) and/or name."""
    params = {"per_page": 100}
    if record_type:
        params["type"] = record_type.upper()
    if name:
        params["name"] = name
    resp = await _get(f"/zones/{zone_id}/dns_records", params)
    if resp.get("success"):
        records = resp["result"]
        lines = []
        for r in records:
            proxied = "proxied" if r.get("proxied") else "dns-only"
            ttl = r.get("ttl", "auto")
            lines.append(f"{r['id']}  {r['type']:6} {r['name']:40} -> {r['content']:30} TTL={ttl} {proxied}")
        return "\n".join(lines) if lines else "No records found"
    return _fmt(resp)

@mcp.tool()
async def dns_create(
    zone_id: str,
    record_type: str,
    name: str,
    content: str,
    proxied: bool = True,
    ttl: int = 1,
    priority: Optional[int] = None,
) -> str:
    """Create a DNS record. type: A, AAAA, CNAME, MX, TXT, SRV, etc. TTL=1 means auto. Priority for MX records."""
    data = {"type": record_type.upper(), "name": name, "content": content, "proxied": proxied, "ttl": ttl}
    if priority is not None:
        data["priority"] = priority
    return _fmt(await _post(f"/zones/{zone_id}/dns_records", data))

@mcp.tool()
async def dns_update(
    zone_id: str,
    record_id: str,
    record_type: Optional[str] = None,
    name: Optional[str] = None,
    content: Optional[str] = None,
    proxied: Optional[bool] = None,
    ttl: Optional[int] = None,
) -> str:
    """Update an existing DNS record. Only provide fields you want to change."""
    # Fetch current record first
    current = await _get(f"/zones/{zone_id}/dns_records/{record_id}")
    if not current.get("success"):
        return _fmt(current)
    rec = current["result"]
    data = {
        "type": (record_type or rec["type"]).upper(),
        "name": name or rec["name"],
        "content": content or rec["content"],
        "proxied": proxied if proxied is not None else rec.get("proxied", False),
        "ttl": ttl or rec.get("ttl", 1),
    }
    return _fmt(await _put(f"/zones/{zone_id}/dns_records/{record_id}", data))

@mcp.tool()
async def dns_delete(zone_id: str, record_id: str) -> str:
    """Delete a DNS record by zone_id and record_id."""
    resp = await _delete(f"/zones/{zone_id}/dns_records/{record_id}")
    if resp.get("success"):
        return f"Deleted record {record_id}"
    return _fmt(resp)

@mcp.tool()
async def dns_export(zone_id: str) -> str:
    """Export all DNS records for a zone in BIND format."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{CF_API}/zones/{zone_id}/dns_records/export", headers=_headers())
        return r.text


# ── SSL/TLS ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def ssl_get(zone_id: str) -> str:
    """Get current SSL/TLS encryption mode for a zone (off, flexible, full, strict)."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/ssl"))

@mcp.tool()
async def ssl_set(zone_id: str, value: str) -> str:
    """Set SSL/TLS encryption mode: off, flexible, full, strict."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/ssl", {"value": value}))

@mcp.tool()
async def always_https_get(zone_id: str) -> str:
    """Check if Always Use HTTPS is enabled for a zone."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/always_use_https"))

@mcp.tool()
async def always_https_set(zone_id: str, value: str) -> str:
    """Enable or disable Always Use HTTPS. value: on or off."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/always_use_https", {"value": value}))


# ── CACHE ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def cache_purge_all(zone_id: str) -> str:
    """Purge ALL cached content for a zone. Use with caution."""
    return _fmt(await _post(f"/zones/{zone_id}/purge_cache", {"purge_everything": True}))

@mcp.tool()
async def cache_purge_urls(zone_id: str, urls: list[str]) -> str:
    """Purge specific URLs from cache. Provide a list of full URLs."""
    return _fmt(await _post(f"/zones/{zone_id}/purge_cache", {"files": urls}))

@mcp.tool()
async def cache_level_get(zone_id: str) -> str:
    """Get current cache level setting (aggressive, basic, simplified)."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/cache_level"))

@mcp.tool()
async def cache_level_set(zone_id: str, value: str) -> str:
    """Set cache level: aggressive, basic, or simplified."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/cache_level", {"value": value}))

@mcp.tool()
async def dev_mode_get(zone_id: str) -> str:
    """Check if Development Mode is enabled (bypasses cache for 3 hours)."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/development_mode"))

@mcp.tool()
async def dev_mode_set(zone_id: str, value: str) -> str:
    """Toggle Development Mode: on or off. Bypasses cache for 3 hours when on."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/development_mode", {"value": value}))


# ── FIREWALL / SECURITY ──────────────────────────────────────────────────────

@mcp.tool()
async def security_level_get(zone_id: str) -> str:
    """Get current security level (off, essentially_off, low, medium, high, under_attack)."""
    return _fmt(await _get(f"/zones/{zone_id}/settings/security_level"))

@mcp.tool()
async def security_level_set(zone_id: str, value: str) -> str:
    """Set security level: off, essentially_off, low, medium, high, under_attack."""
    return _fmt(await _patch(f"/zones/{zone_id}/settings/security_level", {"value": value}))

@mcp.tool()
async def waf_rules_list(zone_id: str) -> str:
    """List WAF custom rules (firewall rules) for a zone."""
    return _fmt(await _get(f"/zones/{zone_id}/firewall/rules", {"per_page": 100}))

@mcp.tool()
async def ip_access_rules_list(zone_id: str) -> str:
    """List IP access rules (allowlist/blocklist) for a zone."""
    return _fmt(await _get(f"/zones/{zone_id}/firewall/access_rules/rules", {"per_page": 100}))

@mcp.tool()
async def ip_access_rule_create(
    zone_id: str,
    target: str,
    value: str,
    mode: str = "block",
    notes: str = "",
) -> str:
    """Create IP access rule. target: ip/ip_range/country. mode: block, challenge, whitelist, js_challenge."""
    data = {"mode": mode, "configuration": {"target": target, "value": value}, "notes": notes}
    return _fmt(await _post(f"/zones/{zone_id}/firewall/access_rules/rules", data))


# ── PAGE RULES ───────────────────────────────────────────────────────────────

@mcp.tool()
async def page_rules_list(zone_id: str) -> str:
    """List all page rules for a zone."""
    return _fmt(await _get(f"/zones/{zone_id}/pagerules"))

@mcp.tool()
async def page_rule_create(
    zone_id: str,
    url_pattern: str,
    actions: list[dict],
    priority: int = 1,
    status: str = "active",
) -> str:
    """Create a page rule. actions is a list of {id, value} dicts. Example: [{"id": "forwarding_url", "value": {"url": "https://...", "status_code": 301}}]"""
    data = {"targets": [{"target": "url", "constraint": {"operator": "matches", "value": url_pattern}}],
            "actions": actions, "priority": priority, "status": status}
    return _fmt(await _post(f"/zones/{zone_id}/pagerules", data))


# ── REDIRECTS (Bulk) ─────────────────────────────────────────────────────────

@mcp.tool()
async def redirect_rules_list(zone_id: str) -> str:
    """List redirect rules (Single Redirects) for a zone."""
    return _fmt(await _get(f"/zones/{zone_id}/rulesets", {"phase": "http_request_dynamic_redirect"}))


# ── ZONE SETTINGS ────────────────────────────────────────────────────────────

@mcp.tool()
async def zone_settings_list(zone_id: str) -> str:
    """List all settings for a zone (minify, polish, rocket_loader, etc)."""
    resp = await _get(f"/zones/{zone_id}/settings")
    if resp.get("success"):
        import json
        settings = resp["result"]
        lines = []
        for s in settings:
            val = s.get("value", "")
            if isinstance(val, dict):
                val = json.dumps(val)
            lines.append(f"{s['id']:30} = {val}")
        return "\n".join(sorted(lines))
    return _fmt(resp)

@mcp.tool()
async def zone_setting_set(zone_id: str, setting_id: str, value: str) -> str:
    """Update a specific zone setting. Use zone_settings_list to see available settings and current values."""
    import json
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        parsed = value
    return _fmt(await _patch(f"/zones/{zone_id}/settings/{setting_id}", {"value": parsed}))


# ── ANALYTICS ────────────────────────────────────────────────────────────────

@mcp.tool()
async def zone_analytics(
    zone_id: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> str:
    """Get zone analytics (requests, bandwidth, threats, pageviews). since/until in ISO format or relative (-1440 = last 24h in minutes)."""
    params = {}
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    return _fmt(await _get(f"/zones/{zone_id}/analytics/dashboard", params))


# ── HEALTH CHECK ─────────────────────────────────────────────────────────────

@mcp.tool()
async def cf_health() -> str:
    """Verify Cloudflare API connectivity and list available zones."""
    resp = await _get("/zones", {"per_page": 50})
    if resp.get("success"):
        zones = resp["result"]
        return f"Connected. {len(zones)} zones: {', '.join(z['name'] for z in zones)}"
    return _fmt(resp)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
