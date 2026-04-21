# tests/test_compliance.py
"""Tests for compliance document generation."""

from compliance.documents import (
    generate_consent_text,
    generate_privacy_policy,
    generate_rkn_notification_json,
    hash_consent,
)


class TestComplianceDocuments:
    """Test 152-FZ compliance document generators."""

    def test_privacy_policy_contains_company_name(self) -> None:
        """Generated policy should include company name."""
        tenant = {"name": "Test Restaurant", "inn": "1234567890"}
        policy = generate_privacy_policy(tenant)
        assert "Test Restaurant" in policy  # nosec B101
        assert "1234567890" in policy  # nosec B101

    def test_consent_text_contains_version(self) -> None:
        """Consent text should include version number."""
        text = generate_consent_text(version=2)
        assert "версия 2" in text  # nosec B101

    def test_hash_consent_deterministic(self) -> None:
        """Hash should be deterministic for same input."""
        text = "consent text"
        assert hash_consent(text) == hash_consent(text)  # nosec B101

    def test_rkn_notification_structure(self) -> None:
        """RKN JSON should have required structure."""
        tenant = {"name": "Test", "inn": "123"}
        data = generate_rkn_notification_json(tenant)
        assert data["operator"]["name"] == "Test"  # nosec B101
        assert data["processing"]["cross_border"] is False  # nosec B101
