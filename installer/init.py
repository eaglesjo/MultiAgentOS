"""Apply VYRELON project bootstrap files."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.profile import DetectionResult


class ProjectInitializer:
    def apply(self, project_root: Path, detections: tuple[DetectionResult, ...]) -> Path:
        target = project_root / ".multiagentos"
        target.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "profiles": [
                {
                    "id": result.profile_id,
                    "confidence": result.confidence,
                    "evidence": list(result.evidence),
                }
                for result in detections
            ],
        }
        config = target / "profile.json"
        config.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return config
