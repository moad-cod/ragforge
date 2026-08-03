import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from app.core.config import settings
from app.services import bronze_storage


class BronzeStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        bronze_storage._bronze_bucket_checked = False

    def tearDown(self) -> None:
        bronze_storage._bronze_bucket_checked = False

    def test_upload_validates_bucket_and_uses_idempotent_object_key(self):
        client = Mock()
        with (
            patch.object(settings, "MINIO_BUCKET_BRONZE", "bronze"),
            patch.object(bronze_storage, "_client", return_value=client),
        ):
            first = bronze_storage.upload_raw_file(
                b"pdf bytes",
                "bronze/org_id=o/project_id=p/document_id=d/version=1/raw/self-attention.pdf",
                "application/pdf",
            )
            second = bronze_storage.upload_raw_file(
                b"pdf bytes",
                "bronze/org_id=o/project_id=p/document_id=d/version=1/raw/self-attention.pdf",
                "application/pdf",
            )

        self.assertEqual(first, second)
        client.head_bucket.assert_called_once_with(Bucket="bronze")
        self.assertEqual(client.put_object.call_count, 2)
        self.assertEqual(
            client.put_object.call_args.kwargs["Key"],
            "org_id=o/project_id=p/document_id=d/version=1/raw/self-attention.pdf",
        )

    def test_missing_bucket_fails_before_put(self):
        client = Mock()
        client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "missing"}},
            "HeadBucket",
        )

        with (
            patch.object(settings, "MINIO_BUCKET_BRONZE", "bronze"),
            patch.object(bronze_storage, "_client", return_value=client),
            self.assertRaisesRegex(RuntimeError, "Bronze bucket 'bronze' does not exist"),
        ):
            bronze_storage.upload_raw_file(b"data", "bronze/key.txt")

        client.put_object.assert_not_called()


if __name__ == "__main__":
    unittest.main()
