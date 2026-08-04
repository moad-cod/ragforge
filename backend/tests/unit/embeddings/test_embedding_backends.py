import unittest
from unittest.mock import patch

from app.core.config import settings
from app.services import embedder
from app.services.retrieval import sparse


class EmbeddingBackendTests(unittest.TestCase):
    def tearDown(self):
        embedder._model = None
        embedder._model_name = None
        embedder._model_loaded_at = None

    def test_deterministic_dense_embeddings_are_stable_and_lexical(self):
        with patch.object(settings, "EMBEDDING_BACKEND", "deterministic"):
            first = embedder.embed_query("bronze silver qdrant")
            repeated = embedder.embed_query("bronze silver qdrant")
            different = embedder.embed_query("unrelated tokens")

        self.assertEqual(len(first), 384)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, different)

    def test_deterministic_sparse_embeddings_share_token_indices(self):
        with patch.object(settings, "EMBEDDING_BACKEND", "deterministic"):
            document = sparse.embed_sparse(["postgres lineage qdrant"])[0]
            query = sparse.embed_sparse_query("qdrant lineage")

        self.assertTrue(set(document.indices).intersection(query.indices))
        self.assertEqual(document.indices, sorted(document.indices))

    def test_unknown_embedding_backend_is_rejected(self):
        with patch.object(settings, "EMBEDDING_BACKEND", "unknown"):
            with self.assertRaisesRegex(ValueError, "Unsupported embedding backend"):
                embedder.embed_query("question")

    def test_auto_embedding_device_resolves_to_cpu_metadata(self):
        with patch.object(settings, "EMBEDDING_DEVICE", "auto"):
            self.assertEqual(embedder.resolve_embedding_device(), "cpu")

    def test_unsupported_embedding_device_fails_before_model_load(self):
        with patch.object(settings, "EMBEDDING_DEVICE", "cuda"):
            with self.assertRaisesRegex(RuntimeError, "not available"):
                embedder.ensure_embedding_model_ready("fake/model")

    def test_fastembed_model_is_loaded_once_per_worker(self):
        constructed = []

        class FakeTextEmbedding:
            def __init__(self, model_name):
                constructed.append(model_name)

            def passage_embed(self, texts):
                return [[1.0, 0.0, 0.0] for _text in texts]

        with (
            patch.object(settings, "EMBEDDING_BACKEND", "fastembed"),
            patch.object(settings, "EMBEDDING_MODEL", "fake/model"),
            patch.object(settings, "EMBEDDING_DIMENSION", 3),
            patch.object(embedder, "_fastembed_class", return_value=FakeTextEmbedding),
        ):
            first = embedder.ensure_embedding_model_ready()
            second = embedder.ensure_embedding_model_ready()
            vectors = embedder.embed_texts(["a", "b"])

        self.assertEqual(constructed, ["fake/model"])
        self.assertTrue(first.loaded)
        self.assertTrue(second.loaded)
        self.assertEqual(len(vectors), 2)


if __name__ == "__main__":
    unittest.main()
