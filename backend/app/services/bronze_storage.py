import boto3
from botocore.config import Config

from app.core.config import settings


_minio = None


def _client():
    global _minio
    if _minio is None:
        _minio = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
    return _minio


def object_key(bronze_path: str) -> str:
    prefix = f"{settings.MINIO_BUCKET_BRONZE}/"
    return bronze_path[len(prefix):] if bronze_path.startswith(prefix) else bronze_path


def upload_raw_file(data: bytes, bronze_path: str, content_type: str | None = None) -> str:
    key = object_key(bronze_path)
    parameters = {
        "Bucket": settings.MINIO_BUCKET_BRONZE,
        "Key": key,
        "Body": data,
    }
    if content_type:
        parameters["ContentType"] = content_type
    _client().put_object(**parameters)
    return f"{settings.MINIO_BUCKET_BRONZE}/{key}"


def raw_file_exists(bronze_path: str) -> bool:
    _client().head_object(
        Bucket=settings.MINIO_BUCKET_BRONZE,
        Key=object_key(bronze_path),
    )
    return True


def delete_raw_file(bronze_path: str) -> None:
    _client().delete_object(
        Bucket=settings.MINIO_BUCKET_BRONZE,
        Key=object_key(bronze_path),
    )
