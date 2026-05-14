"""Millyweb File Transfer MCP — MinIO bridge for Claude container -> VPS2 filesystem."""
import os, json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from minio import Minio
from minio.error import S3Error
from mcp.server.fastmcp import FastMCP

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9002")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "milly-admin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
MINIO_EXTERNAL_ENDPOINT = os.environ.get("MINIO_EXTERNAL_ENDPOINT", "s3.millyweb.com")
SAFE_BASES = ["/opt/data/working-kb", "/opt/data", "/opt/projects", "/tmp"]
mcp = FastMCP("transfer_mcp", host="0.0.0.0", port=8000)

def get_client(): return Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=MINIO_SECURE)
def get_presign_client(): return Minio(MINIO_EXTERNAL_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=True)
def is_safe_path(path): return any(str(Path(path).resolve()).startswith(b) for b in SAFE_BASES)

class DistributeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    bucket: str = Field(default="transfers")
    object_path: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    overwrite: bool = Field(default=True)

class ListInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    bucket: str = Field(default="transfers")
    prefix: str = Field(default="")
    max_results: int = Field(default=50, ge=1, le=200)

class PresignInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    bucket: str = Field(default="transfers")
    object_path: str = Field(..., min_length=1)
    expires_hours: int = Field(default=24, ge=1, le=168)

class UploadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    source: str = Field(..., min_length=1)
    bucket: str = Field(default="documents")
    object_path: str = Field(default="")

class CleanupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    bucket: str = Field(default="transfers")
    prefix: str = Field(default="")
    older_than_hours: int = Field(default=72, ge=1)
    dry_run: bool = Field(default=True)

@mcp.tool(name="transfer_distribute", annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True})
async def transfer_distribute(params: DistributeInput) -> str:
    """Pull file from MinIO and place on VPS2 filesystem. Upload first via: aws --endpoint-url https://s3.millyweb.com s3 cp /home/claude/file s3://bucket/path --no-verify-ssl"""
    if not is_safe_path(params.destination): return json.dumps({"error": f"Destination not in allowed paths: {SAFE_BASES}"})
    dest = Path(params.destination)
    if dest.exists() and not params.overwrite: return json.dumps({"error": f"File exists and overwrite=false"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        get_client().fget_object(params.bucket, params.object_path, str(dest))
        stat = dest.stat()
        return json.dumps({"status": "distributed", "source": f"minio://{params.bucket}/{params.object_path}", "destination": str(dest), "size_bytes": stat.st_size, "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()}, indent=2)
    except S3Error as e: return json.dumps({"error": f"MinIO: {e.code} - {e.message}"})
    except Exception as e: return json.dumps({"error": str(e)})

@mcp.tool(name="transfer_list", annotations={"readOnlyHint": True})
async def transfer_list(params: ListInput) -> str:
    """List objects in a MinIO bucket. Buckets: transfers, documents, assets, builds, backups, uploads."""
    try:
        objs = []
        for obj in get_client().list_objects(params.bucket, prefix=params.prefix or None, recursive=True):
            if len(objs) >= params.max_results: break
            objs.append({"path": obj.object_name, "size_bytes": obj.size, "modified": obj.last_modified.isoformat() if obj.last_modified else None})
        return json.dumps({"bucket": params.bucket, "prefix": params.prefix, "count": len(objs), "objects": objs}, indent=2)
    except S3Error as e: return json.dumps({"error": f"MinIO: {e.code} - {e.message}"})

@mcp.tool(name="transfer_presign", annotations={"readOnlyHint": True})
async def transfer_presign(params: PresignInput) -> str:
    """Generate presigned URL for a MinIO object."""
    try:
        url = get_presign_client().presigned_get_object(params.bucket, params.object_path, expires=timedelta(hours=params.expires_hours))
        return json.dumps({"url": url, "bucket": params.bucket, "object_path": params.object_path, "expires_hours": params.expires_hours}, indent=2)
    except S3Error as e: return json.dumps({"error": f"MinIO: {e.code} - {e.message}"})

@mcp.tool(name="transfer_upload", annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True})
async def transfer_upload(params: UploadInput) -> str:
    """Upload a file from VPS2 filesystem to MinIO."""
    source = Path(params.source)
    if not source.exists(): return json.dumps({"error": f"Source not found: {params.source}"})
    if not source.is_file(): return json.dumps({"error": f"Not a file: {params.source}"})
    obj_path = params.object_path or source.name
    try:
        result = get_client().fput_object(params.bucket, obj_path, str(source))
        return json.dumps({"status": "uploaded", "source": str(source), "destination": f"minio://{params.bucket}/{obj_path}", "size_bytes": source.stat().st_size, "etag": result.etag}, indent=2)
    except S3Error as e: return json.dumps({"error": f"MinIO: {e.code} - {e.message}"})

@mcp.tool(name="transfer_cleanup", annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True})
async def transfer_cleanup(params: CleanupInput) -> str:
    """Remove old objects from MinIO bucket. Defaults dry_run=true."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=params.older_than_hours)
    try:
        candidates = []
        for obj in get_client().list_objects(params.bucket, prefix=params.prefix or None, recursive=True):
            if obj.last_modified and obj.last_modified < cutoff:
                candidates.append({"path": obj.object_name, "size_bytes": obj.size, "modified": obj.last_modified.isoformat()})
        if not params.dry_run and candidates:
            from minio.deleteobjects import DeleteObject
            errs = list(get_client().remove_objects(params.bucket, [DeleteObject(c["path"]) for c in candidates]))
            if errs: return json.dumps({"error": f"Delete errors: {errs}"})
        return json.dumps({"status": "dry_run" if params.dry_run else "cleaned", "bucket": params.bucket, "prefix": params.prefix, "older_than_hours": params.older_than_hours, "objects_affected": len(candidates), "objects": candidates[:50]}, indent=2)
    except S3Error as e: return json.dumps({"error": f"MinIO: {e.code} - {e.message}"})

if __name__ == "__main__": mcp.run(transport="sse")
