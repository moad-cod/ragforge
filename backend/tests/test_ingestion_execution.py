import unittest

from jobs.ingestion_execution import build_job_environment, profile_environment_name


PLAN = {
    "profile": "embedding_aware",
    "command_suffix": "EMBEDDING_AWARE",
    "technique_id": "semantic",
    "resource_class": "high_memory_cpu",
    "embedding_batch_size": 48,
    "max_parallelism": 1,
}


class IngestionExecutionTests(unittest.TestCase):
    def test_profile_specific_command_wins_when_configured(self):
        selected = profile_environment_name(
            "RAGFORGE_SILVER_TO_GOLD_CMD",
            PLAN,
            environment={
                "RAGFORGE_SILVER_TO_GOLD_CMD": "generic",
                "RAGFORGE_SILVER_TO_GOLD_EMBEDDING_AWARE_CMD": "optimized",
            },
        )

        self.assertEqual(
            selected,
            "RAGFORGE_SILVER_TO_GOLD_EMBEDDING_AWARE_CMD",
        )

    def test_generic_command_is_backward_compatible_fallback(self):
        selected = profile_environment_name(
            "RAGFORGE_SILVER_TO_GOLD_CMD",
            PLAN,
            environment={"RAGFORGE_SILVER_TO_GOLD_CMD": "generic"},
        )

        self.assertEqual(selected, "RAGFORGE_SILVER_TO_GOLD_CMD")

    def test_job_environment_contains_resource_hints(self):
        environment = build_job_environment(
            PLAN,
            base_environment={"EXISTING": "preserved"},
        )

        self.assertEqual(environment["EXISTING"], "preserved")
        self.assertEqual(environment["RAGFORGE_INGESTION_PROFILE"], "embedding_aware")
        self.assertEqual(environment["RAGFORGE_INGESTION_TECHNIQUE"], "semantic")
        self.assertEqual(environment["RAGFORGE_EMBEDDING_BATCH_SIZE"], "48")
        self.assertEqual(environment["RAGFORGE_INGESTION_MAX_PARALLELISM"], "1")


if __name__ == "__main__":
    unittest.main()
