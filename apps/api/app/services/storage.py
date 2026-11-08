"""Private storage for KYC document images.

Every file is Fernet-encrypted by the API before it reaches a backend, so
neither the dev folder nor the bucket ever holds a readable document, and
encryption does not depend on the storage vendor. Keys are opaque
(kyc/<business_id>/<uuid>.<ext>). Files are only read back through the API,
which is where PII views get audit-logged; no direct download links exist.
"""

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings
from app.core.security import decrypt_bytes, encrypt_bytes


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("storage key escapes the storage root")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    """Any S3-compatible store (SeaweedFS in docker compose, AWS S3 in prod)."""

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str):
        import boto3

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        )
        existing = {b["Name"] for b in self.client.list_buckets().get("Buckets", [])}
        if bucket not in existing:
            self.client.create_bucket(Bucket=bucket)

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType="application/octet-stream")

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


class EncryptedStorage:
    def __init__(self, inner: Storage):
        self.inner = inner

    def put(self, key: str, data: bytes) -> None:
        self.inner.put(key, encrypt_bytes(data))

    def get(self, key: str) -> bytes:
        return decrypt_bytes(self.inner.get(key))

    def delete(self, key: str) -> None:
        self.inner.delete(key)


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "s3":
        inner: Storage = S3Storage(s.s3_endpoint, s.s3_bucket, s.s3_access_key, s.s3_secret_key)
    else:
        inner = LocalStorage(s.storage_dir)
    return EncryptedStorage(inner)
