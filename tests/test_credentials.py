import os

from runtime.model.credentials import EnvironmentCredentialResolver


def test_credential_check_does_not_expose_values(monkeypatch):
    monkeypatch.setenv("TEST_MODEL_TOKEN", "secret-value")

    result = EnvironmentCredentialResolver().check(["TEST_MODEL_TOKEN"])

    assert result[0].environment_variable == "TEST_MODEL_TOKEN"
    assert result[0].present is True
    assert "secret-value" not in repr(result)


def test_credential_check_reports_missing(monkeypatch):
    monkeypatch.delenv("TEST_MODEL_TOKEN", raising=False)

    result = EnvironmentCredentialResolver().check(["TEST_MODEL_TOKEN"])

    assert result[0].present is False


def test_resolve_returns_environment_value(monkeypatch):
    monkeypatch.setenv("TEST_MODEL_TOKEN", "secret-value")

    assert (
        EnvironmentCredentialResolver().resolve("TEST_MODEL_TOKEN")
        == "secret-value"
    )
