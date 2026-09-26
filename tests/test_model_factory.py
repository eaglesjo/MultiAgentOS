import sys

from runtime.model.factory import ConfiguredAdapterFactory


def test_cli_adapter_factory_builds_generic_adapter():
    adapter = ConfiguredAdapterFactory().build(
        "local-cli",
        {
            "adapter_kind": "cli",
            "command": [sys.executable, "-c", "print('ok')"],
        },
    )
    assert adapter.command[-1] == "print('ok')"


def test_factory_rejects_missing_http_endpoint():
    try:
        ConfiguredAdapterFactory().build(
            "http",
            {"adapter_kind": "http"},
        )
    except ValueError as exc:
        assert "endpoint" in str(exc)
    else:
        raise AssertionError("expected missing endpoint error")
