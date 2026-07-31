import unittest
from importlib.util import find_spec


FASTAPI_AVAILABLE = find_spec("fastapi") is not None


@unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI is not installed")
class ChunkersApiTests(unittest.TestCase):
    def test_get_chunkers_response_does_not_expose_callable_path(self):
        from fastapi.testclient import TestClient
        from app.main import app

        response = TestClient(app).get("/chunkers")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 8)
        self.assertTrue(all("callable_path" not in chunker for chunker in body))

    def test_ingest_validation_rejects_invalid_chunker(self):
        from fastapi import HTTPException
        from app.api.ingest import _validate_text_chunker

        with self.assertRaises(HTTPException) as ctx:
            _validate_text_chunker("xyz")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(
            ctx.exception.detail,
            "Invalid chunker 'xyz'. Available chunkers: "
            "fixed_size, paragraph, sentence, semantic, hierarchical, late_chunking, proposition, multimodal.",
        )


if __name__ == "__main__":
    unittest.main()
