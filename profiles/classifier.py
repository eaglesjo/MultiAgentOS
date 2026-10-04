"""Map detected technology profiles into hierarchical project dimensions."""
from __future__ import annotations

from core.contracts.classification import ClassificationDimension, ProjectClassification
from core.contracts.profile import DetectionResult


_PROFILE_CLASSIFICATION = {
    "android-native": {
        "platform": ("Android",),
        "framework": ("Android Native",),
        "toolchain": ("Gradle",),
        "language": ("Kotlin", "Java"),
    },
    "ios-native": {
        "platform": ("iOS",),
        "framework": ("iOS Native",),
        "toolchain": ("Xcode", "Swift Package Manager"),
        "language": ("Swift", "Objective-C"),
    },
    "react-native": {
        "platform": (),
        "framework": ("React Native",),
        "toolchain": ("Node.js",),
        "language": ("TypeScript", "JavaScript"),
    },
}


def classify_project(detections: tuple[DetectionResult, ...]) -> ProjectClassification:
    platform_values: list[str] = []
    framework_values: list[str] = []
    toolchain_values: list[str] = []
    language_values: list[str] = []
    platform_evidence: list[str] = []
    framework_evidence: list[str] = []
    toolchain_evidence: list[str] = []
    language_evidence: list[str] = []

    for result in detections:
        mapping = _PROFILE_CLASSIFICATION.get(result.profile_id)
        if not mapping:
            continue
        platform_values.extend(mapping["platform"])
        framework_values.extend(mapping["framework"])
        toolchain_values.extend(mapping["toolchain"])
        language_values.extend(mapping["language"])
        platform_evidence.extend(f"{result.profile_id}:{item}" for item in result.evidence)
        framework_evidence.extend(f"{result.profile_id}:{item}" for item in result.evidence)
        toolchain_evidence.extend(f"{result.profile_id}:{item}" for item in result.evidence)
        language_evidence.extend(f"{result.profile_id}:{item}" for item in result.evidence)

    platform_values = list(dict.fromkeys(platform_values))
    framework_values = list(dict.fromkeys(framework_values))
    toolchain_values = list(dict.fromkeys(toolchain_values))
    language_values = list(dict.fromkeys(language_values))

    top_confidence = detections[0].confidence if detections else 0.0
    framework_confidence = top_confidence if framework_values else 0.0

    # RN identifies a framework/runtime but not a native platform by itself.
    # Multiple native profiles identify a real multi-platform project.
    platform_confidence = (
        top_confidence
        if len(platform_values) == 1
        else (min(r.confidence for r in detections) if platform_values else 0.0)
    )

    reasons: list[str] = []
    ambiguous = False
    if len(platform_values) > 1:
        ambiguous = True
        reasons.append("multiple platforms detected")
    if "React Native" in framework_values and not platform_values:
        ambiguous = True
        reasons.append("React Native detected without an explicit native platform")
    if len(language_values) > 1:
        # Kotlin/Java and Swift/Objective-C are paired language families; this is
        # useful information, not ambiguity. More than two families is ambiguous.
        families = {
            "JVM" if value in {"Kotlin", "Java"} else
            "Apple" if value in {"Swift", "Objective-C"} else
            value
            for value in language_values
        }
        if len(families) > 1:
            ambiguous = True
            reasons.append("multiple language families detected")

    return ProjectClassification(
        platform=ClassificationDimension(
            "Platform", tuple(platform_values), platform_confidence, tuple(platform_evidence)
        ),
        framework_runtime=ClassificationDimension(
            "Framework / Runtime", tuple(framework_values), framework_confidence, tuple(framework_evidence)
        ),
        language_toolchain=ClassificationDimension(
            "Language / Toolchain",
            tuple(dict.fromkeys(toolchain_values + language_values)),
            top_confidence if (toolchain_values or language_values) else 0.0,
            tuple(toolchain_evidence + language_evidence),
        ),
        ambiguous=ambiguous,
        reasons=tuple(reasons),
    )
