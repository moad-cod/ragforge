import importlib
import sys
import unittest

from app.services.chunkers.registry import (
    available_chunker_ids,
    get_default_chunker,
    get_chunker,
    list_chunkers,
    validate_chunker,
)


PUBLIC_CHUNKERS = [
    "fixed_size",
    "paragraph",
    "sentence",
    "semantic",
    "hierarchical",
    "late_chunking",
    "proposition",
    "multimodal",
]

REQUIRED_FIELDS = {
    "id",
    "name",
    "tier",
    "status",
    "is_beta",
    "short_description",
    "long_description",
    "best_for",
    "not_recommended_for",
    "speed_level",
    "quality_level",
    "cost_level",
    "requires_llm",
    "requires_nltk",
    "requires_embedding_model",
    "requires_multimodal",
    "default",
}


class ChunkerRegistryTests(unittest.TestCase):
    def test_list_chunkers_returns_all_public_chunkers(self):
        self.assertEqual([chunker["id"] for chunker in list_chunkers()], PUBLIC_CHUNKERS)

    def test_paragraph_is_default(self):
        self.assertEqual(get_default_chunker().id, "paragraph")
        defaults = [chunker for chunker in list_chunkers() if chunker["default"]]
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0]["id"], "paragraph")

    def test_proposition_is_beta(self):
        proposition = next(chunker for chunker in list_chunkers() if chunker["id"] == "proposition")
        self.assertEqual(proposition["status"], "beta")
        self.assertIs(proposition["is_beta"], True)

    def test_multimodal_is_experimental(self):
        multimodal = next(chunker for chunker in list_chunkers() if chunker["id"] == "multimodal")
        self.assertEqual(multimodal["status"], "experimental")
        self.assertIs(multimodal["requires_multimodal"], True)

    def test_invalid_chunker_raises_clean_error(self):
        with self.assertRaises(ValueError) as ctx:
            validate_chunker("xyz")
        self.assertEqual(
            str(ctx.exception),
            "Invalid chunker 'xyz'. Available chunkers: "
            "fixed_size, paragraph, sentence, semantic, hierarchical, late_chunking, proposition, multimodal.",
        )

    def test_public_metadata_does_not_expose_callable_paths(self):
        for chunker in list_chunkers():
            self.assertNotIn("callable_path", chunker)
            self.assertNotIn("callable", chunker)
            self.assertNotIn("internal", chunker)

    def test_registry_import_does_not_load_heavy_chunker_modules(self):
        heavy_modules = [
            "app.services.chunkers.semantic",
            "app.services.chunkers.late_chunking",
            "app.services.chunkers.proposition",
            "app.services.chunkers.multimodal",
            "sentence_transformers",
            "torch",
            "colpali_engine",
        ]
        for module in heavy_modules:
            sys.modules.pop(module, None)

        registry = importlib.import_module("app.services.chunkers.registry")
        importlib.reload(registry)

        for module in heavy_modules:
            self.assertNotIn(module, sys.modules)

    def test_all_public_chunkers_have_complete_metadata(self):
        for chunker in list_chunkers():
            self.assertEqual(set(chunker), REQUIRED_FIELDS)
            self.assertTrue(chunker["id"])
            self.assertTrue(chunker["name"])
            self.assertTrue(chunker["best_for"])
            self.assertTrue(chunker["not_recommended_for"])

    def test_internal_files_are_not_exposed_as_chunkers(self):
        ids = available_chunker_ids()
        self.assertNotIn("registry", ids)
        self.assertNotIn("tokenize", ids)
        self.assertNotIn("__init__", ids)
        self.assertNotIn("__pycache__", ids)

    def test_get_chunker_lazy_loads_callable(self):
        chunker = get_chunker("paragraph")
        self.assertTrue(callable(chunker))


if __name__ == "__main__":
    unittest.main()
