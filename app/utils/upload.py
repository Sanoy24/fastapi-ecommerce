"""
File upload utility — supports local disk and S3/compatible storage.

Storage backend is controlled by the STORAGE_BACKEND setting:
  "local" → saves files under UPLOAD_DIR (default: ./uploads)
  "s3"    → uploads to S3_BUCKET using boto3 (install boto3 separately)
"""
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile, HTTPException, status

from app.core.config import settings
from app.core.logger import logger

try:
    import boto3  # type: ignore
    from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False
    logger.warning("boto3 not installed. S3 upload will not work.")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def _validate_image(file: UploadFile) -> None:
    """Validate content-type and size before upload."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: JPEG, PNG, WebP, GIF.",
        )


def _generate_filename(original_filename: Optional[str]) -> str:
    """Generate a unique filename preserving the original extension."""
    ext = Path(original_filename or "upload.jpg").suffix.lower() or ".jpg"
    return f"{uuid.uuid4().hex}{ext}"


async def save_product_image(file: UploadFile) -> str:
    """
    Save a product image and return its public URL / relative path.

    Reads up to MAX_IMAGE_SIZE_BYTES of data; rejects oversized files.

    Returns:
        str: URL string (local relative path or S3 URL)
    """
    _validate_image(file)

    contents = await file.read(MAX_IMAGE_SIZE_BYTES + 1)
    if len(contents) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB limit.",
        )

    filename = _generate_filename(file.filename)

    if settings.STORAGE_BACKEND == "s3":
        return await _upload_to_s3(contents, filename, file.content_type)
    else:
        return await _save_locally(contents, filename)


async def _save_locally(contents: bytes, filename: str) -> str:
    """Save file to local UPLOAD_DIR and return relative path."""
    upload_dir = Path(settings.UPLOAD_DIR) / "products"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / filename
    with open(file_path, "wb") as f:
        f.write(contents)

    logger.info(f"Image saved locally: {file_path}")
    # Return a relative URL; the caller should serve UPLOAD_DIR as static
    return f"/{settings.UPLOAD_DIR}/products/{filename}"


async def _upload_to_s3(contents: bytes, filename: str, content_type: str) -> str:
    """Upload file to S3 and return the public URL."""
    if not _BOTO3_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 storage requires boto3. Install with: pip install boto3",
        )

    try:
        s3_client = boto3.client(
            "s3",
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY,
        )
        key = f"products/{filename}"
        s3_client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=contents,
            ContentType=content_type,
            ACL="public-read",
        )
        url = f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{key}"
        logger.info(f"Image uploaded to S3: {url}")
        return url
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image. Please try again.",
        )
