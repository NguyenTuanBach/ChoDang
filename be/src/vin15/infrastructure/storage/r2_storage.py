from __future__ import annotations

from typing import Any


class R2FileStorage:
    """Cloudflare R2 qua API S3 (boto3). Bucket riêng tư; không tạo URL công khai."""

    def __init__(self, endpoint: str, access_key_id: str, secret_access_key: str, bucket: str, client: Any = None):
        self._bucket = bucket
        if client is None:
            import boto3  # nhập muộn: chỉ cần khi thật sự dùng R2

            client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name="auto",
            )
        self._client = client

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey as error:
            raise FileNotFoundError(key) from error
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
