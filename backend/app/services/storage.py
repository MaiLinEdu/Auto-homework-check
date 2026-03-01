"""S3-compatible object storage service."""

import uuid

import boto3
from fastapi import UploadFile

from app.core.config import settings


class StorageService:
    """Handles file uploads to S3-compatible storage (MinIO in dev, S3 in prod)."""

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )
        self.bucket = settings.S3_BUCKET_NAME

    async def upload_file(self, file: UploadFile, prefix: str = "") -> str:
        """Upload a file and return its storage key."""
        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
        key = f"{prefix}/{uuid.uuid4()}.{ext}".lstrip("/")

        content = await file.read()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
        )
        return key

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading a file."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_file(self, key: str) -> None:
        """Delete a file from storage."""
        self.client.delete_object(Bucket=self.bucket, Key=key)
