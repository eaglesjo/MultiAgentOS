import json
import sys

from multiagentos.cli import main


def test_models_run_executes_declared_cli_adapter(tmp_path, capsys):
    config_dir = tmp_path / ".multiagentos"
    config_dir.mkdir()
    config = {
        "providers": [
            {
                "id": "local",
                "kind": "cli",
                "models": [
                    {
                        "id": "echo-model",
                        "capabilities": ["execution", "validation"],
                        "metadata": {
                            "adapter_id": "echo-cli",
                            "adapter_kind": "cli",
                            "command": [
                                sys.executable,
                                "-c",
                                "import sys; print('MODEL:' + sys.stdin.read())",
                            ],
                        },
                    }
                ],
            }
        ]
    }
    (config_dir / "providers.json").write_text(
        json.dumps(config), encoding="utf-8"
    )

    assert (
        main(
            [
                "models",
                "run",
                str(tmp_path),
                "--model",
                "echo-model",
                "--objective",
                "hello",
            ]
        )
        == 0
    )
    assert "MODEL:hello" in capsys.readouterr().out
