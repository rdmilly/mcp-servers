"""Millyweb File Transfer MCP.

Bridges Claude's container → MinIO → VPS2 filesystem.
Handles distribution, listing, presigned URLs, and cleanup.

Workflow:
  1. Claude uploads to MinIO via AWS CLI (from its container)
  2. Claude calls transfer_distribute to place file on VPS2
  3. Optionally generate shareable presigned URLs
"""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from minio import Minio
from minio.error import S3Error
from mcp.server.fastmcp import FastMCP

# Configuration
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9002")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "milly-admin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
MINIO_EXTERNAL_ENDPOINT = os.environ.get("MINIO_EXTERNAL_ENDPOINT", "s3.millyweb.com")
DEFAULT_BUCKET = os.environ.get("DEFAULT_BUCKET", "transfers")

# Known safe base paths for distribution
SAFE_BASES = [
    "/opt/data/working-kb",
    "/opt/data",
    "/opt/projects",
    "/tmp",
]

mcp = FastMCP("transfer_mcp", host="0.0.0.0", port=8000)


def get_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def get_presign_client() -> Minio:
    """Client for presigned URLs - uses external endpoint so signatures match."""
    return Minio(
        MINIO_EXTERNAL_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=True,
    )


def is_safe_path(path: str) -> bool:
    """Ensure destination is under an allowed base path."""
    resolved = str(Path(path).resolve())
    return any(resolved.startswith(base) for base in SAFE_BASES)


# ─── Input Models ───────────────────────────────────────────

class DistributeInput(BaseModel):
    """Pull a file from MinIO and place it on the VPS2 filesystem."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    bucket: str = Field(
        default="transfers",
        description="MinIO bucket name (transfers, documents, assets, builds, backups, uploads)",
    )
    object_path: str = Field(
        ...,
        description="Object path within the bucket (e.g. 'specs/design.md')",
        min_length=1,
    )
    destination: str = Field(
        ...,
        description="Absolute path on VPS2 filesystem (e.g. '/opt/data/working-kb/specs/design.md')",
        min_length=1,
    )
    overwrite: bool = Field(
        default=True,
        description="Overwrite if destination exists",
    )


class ListInput(BaseModel):
    """List objects in a MinIO bucket."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    bucket: str = Field(
        default="transfers",
        description="MinIO bucket name",
    )
    prefix: str = Field(
        default="",
        description="Filter by path prefix (e.g. 'specs/' or 'backups/2026-02')",
    )
    max_results: int = Field(
        default=50,
        description="Maximum objects to return",
        ge=1,
        le=200,
    )


class PresignInput(BaseModel):
    """Generate a presigned URL for a MinIO object."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    bucket: str = Field(
        default="transfers",
        description="MinIO bucket name",
    )
    object_path: str = Field(
        ...,
        description="Object path within the bucket",
        min_length=1,
    )
    expires_hours: int = Field(
        default=24,
        description="URL expiration in hours (1-168, default 24)",
        ge=1,
        le=168,
    )


class UploadInput(BaseModel):
    """Upload a local VPS2 file to MinIO."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source: str = Field(
        ...,
        description="Absolute path to file on VPS2 (e.g. '/opt/data/working-kb/specs/design.md')",
        min_length=1,
    )
    bucket: str = Field(
        default="documents",
        description="Destination MinIO bucket",
    )
    object_path: str = Field(
        default="",
        description="Destination path in bucket. If empty, uses the filename.",
    )


class CleanupInput(BaseModel):
    """Remove old files from a MinIO bucket prefix."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    bucket: str = Field(
        default="transfers",
        description="MinIO bucket to clean",
    )
    prefix: str = Field(
        default="",
        description="Only clean objects under this prefix",
    )
    older_than_hours: int = Field(
        default=72,
        description="Remove objects older than N hours (default 72)",
        ge=1,
    )
    dry_run: bool = Field(
        default=True,
        description="If true, list what would be deleted without deleting",
    )


# ─── Tools ──────────────────────────────────────────────────

@mcp.tool(
    name="transfer_distribute",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
)
async def transfer_distribute(params: DistributeInput) -> str:
    """Pull a file from MinIO and place it on VPS2 filesystem.

    Use after uploading to MinIO from Claude's container via AWS CLI:
      aws --endpoint-url https://s3.millyweb.com s3 cp /home/claude/file s3://bucket/path --no-verify-ssl

    Then call this tool to distribute to the final location.
    """
    if not is_safe_path(params.destination):
        return json.dumps({"error": f"Destination not in allowed paths: {SAFE_BASES}"})

    dest = Path(params.destination)
    if dest.exists() and not params.overwrite:
        return json.dumps({"error": f"File exists and overwrite=false: {params.destination}"})

    # Create parent directories
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        client = get_client()
        client.fget_object(params.bucket, params.object_path, str(dest))
        stat = dest.stat()
        return json.dumps({
            "status": "distributed",
            "source": f"minio://{params.bucket}/{params.object_path}",
            "destination": str(dest),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }, indent=2)
    except S3Error as e:
        return json.dumps({"error": f"MinIO error: {e.code} - {e.message}"})
    except Exception as e:
        return json.dumps({"error": f"Distribution failed: {str(e)}"})


@mcp.tool(
    name="transfer_list",
    annotations={"readOnlyHint": True},
)
async def transfer_list(params: ListInput) -> str:
    """List objects in a MinIO bucket, optionally filtered by prefix.

    Available buckets: transfers, documents, assets, builds, backups,
    contextengine-backups, deploys, uploads, zipline, fleet-exports, temp
    """
    try:
        client = get_client()
        objects = []
        for obj in client.list_objects(params.bucket, prefix=params.prefix or None, recursive=True):
            if len(objects) >= params.max_results:
                break
            objects.append({
                "path": obj.object_name,
                "size_bytes": obj.size,
                "modified": obj.last_modified.isoformat() if obj.last_modified else None,
            })

        return json.dumps({
            "bucket": params.bucket,
            "prefix": params.prefix,
            "count": len(objects),
            "objects": objects,
        }, indent=2)
    except S3Error as e:
        return json.dumps({"error": f"MinIO error: {e.code} - {e.message}"})


@mcp.tool(
    name="transfer_presign",
    annotations={"readOnlyHint": True},
)
async def transfer_presign(params: PresignInput) -> str:
    """Generate a presigned (shareable) URL for a MinIO object.

    URLs are temporary and expire after the specified duration.
    Useful for sharing files externally without MinIO credentials.
    """
    from datetime import timedelta
    try:
        client = get_presign_client()
        url = client.presigned_get_object(
            params.bucket,
            params.object_path,
            expires=timedelta(hours=params.expires_hours),
        )
        return json.dumps({
            "url": url,
            "bucket": params.bucket,
            "object_path": params.object_path,
            "expires_hours": params.expires_hours,
        }, indent=2)
    except S3Error as e:
        return json.dumps({"error": f"MinIO error: {e.code} - {e.message}"})


@mcp.tool(
    name="transfer_upload",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
)
async def transfer_upload(params: UploadInput) -> str:
    """Upload a file FROM the VPS2 filesystem TO MinIO.

    Useful for backing up files, sharing between services,
    or staging files for Claude to download in a future session.
    """
    source = Path(params.source)
    if not source.exists():
        return json.dumps({"error": f"Source file not found: {params.source}"})
    if not source.is_file():
        return json.dumps({"error": f"Source is not a file: {params.source}"})

    object_path = params.object_path or source.name

    try:
        client = get_client()
        result = client.fput_object(params.bucket, object_path, str(source))
        return json.dumps({
            "status": "uploaded",
            "source": str(source),
            "destination": f"minio://{params.bucket}/{object_path}",
            "size_bytes": source.stat().st_size,
            "etag": result.etag,
        }, indent=2)
    except S3Error as e:
        return json.dumps({"error": f"MinIO error: {e.code} - {e.message}"})


@mcp.tool(
    name="transfer_cleanup",
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True},
)
async def transfer_cleanup(params: CleanupInput) -> str:
    """Remove old objects from a MinIO bucket.

    Defaults to dry_run=true so you can preview what would be deleted.
    Set dry_run=false to actually remove files.
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=params.older_than_hours)

    try:
        client = get_client()
        candidates = []
        for obj in client.list_objects(params.bucket, prefix=params.prefix or None, recursive=True):
            if obj.last_modified and obj.last_modified < cutoff:
                candidates.append({
                    "path": obj.object_name,
                    "size_bytes": obj.size,
                    "modified": obj.last_modified.isoformat(),
                })

        if not params.dry_run:
            from minio.deleteobjects import DeleteObject
            delete_list = [DeleteObject(c["path"]) for c in candidates]
            if delete_list:
                errors = list(client.remove_objects(params.bucket, delete_list))
                if errors:
                    return json.dumps({"error": f"Delete errors: {errors}"})

        return json.dumps({
            "status": "dry_run" if params.dry_run else "cleaned",
            "bucket": params.bucket,
            "prefix": params.prefix,
            "older_than_hours": params.older_than_hours,
            "objects_affected": len(candidates),
            "objects": candidates[:50],  # cap output
        }, indent=2)
    except S3Error as e:
        return json.dumps({"error": f"MinIO error: {e.code} - {e.message}"})


if __name__ == "__main__":
    mcp.run(transport="sse")
