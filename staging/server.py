"""Millyweb Staging MCP — VPS2 <-> Windows (Clair/Dave) file transfer via SSH over WireGuard."""
import os, json, subprocess
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

WINDOWS_USER = os.environ.get("WINDOWS_USER", "user")
WINDOWS_HOST = os.environ.get("WINDOWS_HOST", "10.0.0.3")
STAGING_BASE = os.environ.get("STAGING_BASE", r"C:\Users\user\Documents\Staging")
SSH_KEY = os.environ.get("SSH_KEY", "/root/.ssh/id_ed25519")
SSH_OPTS = f"-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o PasswordAuthentication=no -i {SSH_KEY}"
LOCAL_TEMP = "/tmp/staging"
os.makedirs(LOCAL_TEMP, exist_ok=True)
mcp = FastMCP("staging", host="0.0.0.0", port=8000)

def _ssh(cmd): r = subprocess.run(f"ssh {SSH_OPTS} {WINDOWS_USER}@{WINDOWS_HOST} '{cmd}'", shell=True, capture_output=True, text=True, timeout=30); return r.returncode, (r.stdout + r.stderr).strip()
def _scp_to(local, subpath): r = subprocess.run(f"scp {SSH_OPTS} '{local}' {WINDOWS_USER}@{WINDOWS_HOST}:'{STAGING_BASE}\\{subpath}'", shell=True, capture_output=True, text=True, timeout=60); return r.returncode, (r.stdout + r.stderr).strip()
def _scp_from(subpath, local): r = subprocess.run(f"scp {SSH_OPTS} {WINDOWS_USER}@{WINDOWS_HOST}:'{STAGING_BASE}\\{subpath}' '{local}'", shell=True, capture_output=True, text=True, timeout=60); return r.returncode, (r.stdout + r.stderr).strip()

class PushInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    source: str = Field(...)
    subfolder: str = Field(default="Downloads")
    filename: str = Field(default="")

class PullInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filename: str = Field(...)
    subfolder: str = Field(default="Uploads")
    destination: str = Field(default="")
    upload_to_minio: bool = Field(default=False)
    minio_bucket: str = Field(default="uploads")

class ListInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    subfolder: str = Field(default="")

@mcp.tool(name="staging_push")
async def staging_push(params: PushInput) -> str:
    """Push file from VPS2 to Windows Staging. Lands in C:\\Users\\rdmil\\Documents\\Staging\\<subfolder>\\."""
    source = Path(params.source)
    if not source.exists(): return json.dumps({"error": f"Source not found: {params.source}"})
    fname = params.filename or source.name
    rc, out = _scp_to(str(source), f"{params.subfolder}\\{fname}")
    if rc != 0: return json.dumps({"error": f"SCP failed: {out}"})
    return json.dumps({"status": "pushed", "source": str(source), "destination": f"{STAGING_BASE}\\{params.subfolder}\\{fname}", "size_bytes": source.stat().st_size}, indent=2)

@mcp.tool(name="staging_pull")
async def staging_pull(params: PullInput) -> str:
    """Pull file from Windows Staging to VPS2. Optionally upload to MinIO."""
    dest = params.destination or f"{LOCAL_TEMP}/{params.filename}"
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    rc, out = _scp_from(f"{params.subfolder}\\{params.filename}", dest)
    if rc != 0: return json.dumps({"error": f"SCP failed: {out}"})
    result = {"status": "pulled", "source": f"{STAGING_BASE}\\{params.subfolder}\\{params.filename}", "destination": dest, "size_bytes": Path(dest).stat().st_size}
    if params.upload_to_minio:
        try:
            from minio import Minio
            c = Minio(os.environ.get("MINIO_ENDPOINT", "minio:9000"), access_key=os.environ.get("MINIO_ACCESS_KEY", ""), secret_key=os.environ.get("MINIO_SECRET_KEY", ""), secure=False)
            c.fput_object(params.minio_bucket, params.filename, dest)
            result["minio"] = f"minio://{params.minio_bucket}/{params.filename}"
        except Exception as e: result["minio_error"] = str(e)
    return json.dumps(result, indent=2)

@mcp.tool(name="staging_list")
async def staging_list(params: ListInput) -> str:
    """List files in Windows Staging folder."""
    target = f"{STAGING_BASE}\\{params.subfolder}" if params.subfolder else STAGING_BASE
    rc, out = _ssh(f'dir "{target}" /B 2>nul')
    if rc != 0: return json.dumps({"error": f"List failed: {out}"})
    files = [f for f in out.split('\n') if f.strip()] if out else []
    return json.dumps({"path": target, "count": len(files), "files": files}, indent=2)

@mcp.tool(name="staging_status")
async def staging_status() -> str:
    """Check Windows connectivity and staging subfolder file counts."""
    rc, out = _ssh('echo OK')
    if rc != 0: return json.dumps({"status": "offline", "error": out})
    counts = {}
    for sub in ["Downloads", "Uploads", "Documents"]:
        rc2, out2 = _ssh(f'dir "{STAGING_BASE}\\{sub}" /B /A-D 2>nul')
        counts[sub] = len([f for f in out2.split('\n') if f.strip()]) if rc2 == 0 and out2 else 0
    return json.dumps({"status": "online", "host": WINDOWS_HOST, "staging_base": STAGING_BASE, "file_counts": counts}, indent=2)

if __name__ == "__main__": mcp.run(transport="sse")
