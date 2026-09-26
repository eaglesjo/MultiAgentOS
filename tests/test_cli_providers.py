import json
from pathlib import Path

from multiagentos.cli import main


def _write_config(root: Path, environment_variable: str) -> None:
    config = {
        "providers": [
            {
                "id": "provider-a",
                "kind": "http",
                "models": [
                    {
                        "id": "model-a",
                        "capabilities": ["execution"],
                        "metadata": {
                            "adapter_id": "http",
                            "credential_env": [environment_variable],
                        },
                    }
                ],
            }
        ]
    }
    path = root / ".multiagentos"
    path.mkdir()
    (path / "providers.json").write_text(json.dumps(config), encoding="utf-8")


def test_provider_list_command(tmp_path, capsys):
    _write_config(tmp_path, "TEST_MODEL_TOKEN")

    assert main(["providers", "list", str(tmp_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output[0]["id"] == "provider-a"
    assert output[0]["models"][0]["id"] == "model-a"
    assert "TEST_MODEL_TOKEN" not in json.dumps(output)


def test_provider_validate_command_reports_missing_credential(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("TEST_MODEL_TOKEN", raising=False)
    _write_config(tmp_path, "TEST_MODEL_TOKEN")

    assert main(["providers", "validate", str(tmp_path)]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is False
    assert output["models"][0]["credential_environment_variables"][0] == {
        "name": "TEST_MODEL_TOKEN",
        "present": False,
    }


def test_provider_validate_command_accepts_present_credential(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("TEST_MODEL_TOKEN", "secret-value")
    _write_config(tmp_path, "TEST_MODEL_TOKEN")

    assert main(["providers", "validate", str(tmp_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
    assert "secret-value" not in capsys.readouterr().out
