import json
import tempfile
import unittest
from pathlib import Path

from runtime.config.loader import ConfigLoader
from core.routing import RoutingStrategy


class ConfigLoaderTests(unittest.TestCase):
    def test_loads_multi_ai_assignment(self):
        config = {
            "ai": {
                "providers": [
                    {
                        "id": "ai-a",
                        "type": "generic",
                        "models": [
                            {
                                "id": "model-a",
                                "capabilities": ["code"],
                            }
                        ],
                    },
                    {
                        "id": "local",
                        "type": "local",
                        "models": [
                            {
                                "id": "local-code",
                                "capabilities": ["code"],
                            }
                        ],
                    },
                ]
            },
            "agents": [
                {
                    "id": "developer",
                    "role": "developer",
                    "capabilities": ["code"],
                    "models": ["model-a", "local-code"],
                    "strategy": "pool",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = ConfigLoader().load(path)

        self.assertEqual(loaded.agents.get("developer").model_ids, ("model-a", "local-code"))
        self.assertEqual(loaded.routing["developer"], RoutingStrategy.POOL)
        self.assertEqual(len(loaded.ai.models()), 2)


if __name__ == "__main__":
    unittest.main()
