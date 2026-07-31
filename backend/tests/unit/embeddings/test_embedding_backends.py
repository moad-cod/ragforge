import unittest
from unittest.mock import patch

from app.core.config import settings
from app.services import embedder
from app.services.retrieval import sparse


class EmbeddingBackendTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
