import boto3
from botocore.config import Config
from app.core.config import settings

r2 = boto3.client(
    "s3",
    endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

def upload_image(image_bytes: bytes, key: str, content_type: str = "image/png") -> str:
    """Upload image to R2 and return public URL."""
    r2.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=image_bytes,
        ContentType=content_type,
    )
    return f"{settings.R2_PUBLIC_URL}/{key}"

def delete_image(key: str):
    """Delete image from R2."""
    r2.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)

def delete_document_images(document_id: str):
    """Delete all page images for a document."""
    prefix = f"pages/{document_id}/"
    response = r2.list_objects_v2(Bucket=settings.R2_BUCKET_NAME, Prefix=prefix)
    objects = response.get("Contents", [])
    if objects:
        r2.delete_objects(
            Bucket=settings.R2_BUCKET_NAME,
            Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
        )