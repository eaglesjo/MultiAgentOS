import json
import sys

from core.contracts.work_unit import WorkStatus
from multiagentos.cli import main
from runtime.vyrelon import VYRELONRuntime


def _write_config(root):
    config_dir = root / ".multiagentos"
    config_dir.mkdir()
    config = {
        "providers": [
            {
                "id": "local",
                "kind": "cli",
                "models": [
                    {
                        "id": "echo-model",
                        "capabilities": ["execution"],
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


def test_run_model_persists_work_unit(tmp_path, capsys):
    _write_config(tmp_path)

    assert (
        main(
            [
                "run",
                str(tmp_path),
                "--id",
                "persistent-model",
                "--model",
                "echo-model",
                "--objective",
                "hello",
            ]
        )
        == 0
    )

    work = VYRELONRuntime().state_store(tmp_path).load("persistent-model")
    assert work.status == WorkStatus.COMPLETED
    assert work.metadata["runtime"] == "configured-model"
    assert work.metadata["model_id"] == "echo-model"
    assert work.metadata["model_response"] == "MODEL:hello\n"
    assert "MODEL:hello" in capsys.readouterr().out


def test_resume_model_reuses_persisted_configuration(tmp_path, capsys):
    _write_config(tmp_path)
    store = VYRELONRuntime().state_store(tmp_path)

    assert (
        main(
            [
                "run",
                str(tmp_path),
                "--id",
                "resume-model",
                "--model",
                "echo-model",
                "--objective",
                "resume-me",
            ]
        )
        == 0
    )

    work = store.load("resume-model")
    work.status = WorkStatus.EXECUTING
    store.save(work)

    assert main(["resume", "resume-model", str(tmp_path)]) == 0

    restored = store.load("resume-model")
    assert restored.status == WorkStatus.COMPLETED
    assert restored.metadata["model_id"] == "echo-model"
    assert restored.metadata["model_response"] == "MODEL:resume-me\n"
    assert capsys.readouterr().out.endswith("MODEL:resume-me\n")


def test_run_requires_exactly_one_execution_mode(tmp_path):
    try:
        main(
            [
                "run",
                str(tmp_path),
                "--objective",
                "invalid",
            ]
        )
    except ValueError as exc:
        assert str(exc) == "Specify exactly one of --model or --command"
    else:
        raise AssertionError("run should require --model or --command")
