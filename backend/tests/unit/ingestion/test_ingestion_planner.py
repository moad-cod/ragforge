import unittest

from app.services.ingestion_planner import build_ingestion_plan


class IngestionPlannerTests(unittest.TestCase):
    def test_lightweight_chunkers_use_throughput_profile(self):
        plan = build_ingestion_plan("paragraph", source_type="file")

        self.assertEqual(plan.profile, "throughput")
        self.assertEqual(plan.command_suffix, "THROUGHPUT")
        self.assertEqual(plan.embedding_batch_size, 192)
        self.assertEqual(plan.max_parallelism, 4)

    def test_hierarchical_chunking_uses_structured_profile(self):
        plan = build_ingestion_plan("hierarchical")

        self.assertEqual(plan.profile, "structured")
        self.assertEqual(plan.resource_class, "cpu")

    def test_embedding_aware_chunkers_limit_memory_pressure(self):
        for chunker_id in ("semantic", "late_chunking"):
            with self.subTest(chunker_id=chunker_id):
                plan = build_ingestion_plan(chunker_id)
                self.assertEqual(plan.profile, "embedding_aware")
                self.assertEqual(plan.embedding_batch_size, 48)
                self.assertEqual(plan.max_parallelism, 1)

    def test_llm_chunking_uses_rate_limit_safe_profile(self):
        plan = build_ingestion_plan("proposition")

        self.assertEqual(plan.profile, "llm_enriched")
        self.assertEqual(plan.resource_class, "network")
        self.assertTrue(plan.requires_llm)

    def test_multimodal_source_uses_gpu_profile(self):
        plan = build_ingestion_plan("multimodal", source_type="multimodal")

        self.assertEqual(plan.profile, "multimodal")
        self.assertEqual(plan.resource_class, "gpu")
        self.assertEqual(plan.embedding_batch_size, 2)


if __name__ == "__main__":
    unittest.main()
