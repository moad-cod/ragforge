import unittest

from pydantic import ValidationError

from app.api.auth import RegisterRequest, UpdateMeRequest


class AuthOrganizationValidationTests(unittest.TestCase):
    def test_registration_rejects_non_uuid_organization_id(self):
        with self.assertRaisesRegex(
            ValidationError,
            "organization_id must be a valid UUID",
        ):
            RegisterRequest(
                email="user@example.com",
                password="strong-password",
                organization_id="string",
            )

    def test_registration_without_organization_is_valid(self):
        request = RegisterRequest(
            email="user@example.com",
            password="strong-password",
        )

        self.assertIsNone(request.organization_id)

    def test_registration_normalizes_valid_organization_uuid(self):
        request = RegisterRequest(
            email="user@example.com",
            password="strong-password",
            organization_id="10000000-0000-0000-0000-000000000002",
        )

        self.assertEqual(
            request.organization_id,
            "10000000-0000-0000-0000-000000000002",
        )

    def test_profile_update_rejects_non_uuid_organization_id(self):
        with self.assertRaisesRegex(
            ValidationError,
            "organization_id must be a valid UUID",
        ):
            UpdateMeRequest(organization_id="string")

    def test_profile_update_keeps_empty_string_as_clear_request(self):
        request = UpdateMeRequest(organization_id="")

        self.assertEqual(request.organization_id, "")


if __name__ == "__main__":
    unittest.main()
