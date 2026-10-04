"""Build hierarchical classification from direct project evidence.

The classifier does not infer language/toolchain values merely because a
profile was selected. A value is emitted only when its own evidence is present.
"""

from __future__ import annotations

from core.contracts.classification import ClassificationDimension, ProjectClassification
from core.contracts.profile import DetectionResult


def classify_project(detections: tuple[DetectionResult, ...]) -> ProjectClassification:
    platform_values: list[str] = []
    framework_values: list[str] = []
    language_values: list[str] = []
    toolchain_values: list[str] = []
    platform_evidence: list[str] = []
    framework_evidence: list[str] = []
    language_evidence: list[str] = []
    toolchain_evidence: list[str] = []

    top_confidence = detections[0].confidence if detections else 0.0

    for result in detections:
        evidence = set(result.evidence)
        prefix = result.profile_id

        if result.profile_id == "android-native":
            platform_values.append("Android")
            platform_evidence.extend(f"{prefix}:{item}" for item in result.evidence)

            framework_markers = {
                "com.android.application",
                "com.android.library",
                "directory:android",
                "AndroidManifest.xml",
                "libs.plugins.android.application",
                "libs.plugins.android.library",
            }
            if evidence & framework_markers:
                framework_values.append("Android Native")
                framework_evidence.extend(
                    f"{prefix}:{item}"
                    for item in result.evidence
                    if item in framework_markers
                )

            gradle_markers = {
                "settings.gradle",
                "settings.gradle.kts",
                "build.gradle",
                "build.gradle.kts",
                "gradlew",
            }
            if evidence & gradle_markers:
                toolchain_values.append("Gradle")
                toolchain_evidence.extend(
                    f"{prefix}:{item}"
                    for item in result.evidence
                    if item in gradle_markers
                )

            if "source:kotlin" in evidence or "org.jetbrains.kotlin.android" in evidence:
                language_values.append("Kotlin")
                language_evidence.extend(
                    f"{prefix}:{item}"
                    for item in result.evidence
                    if item in {"source:kotlin", "org.jetbrains.kotlin.android"}
                )
            if "source:java" in evidence:
                language_values.append("Java")
                language_evidence.append(f"{prefix}:source:java")

        elif result.profile_id == "ios-native":
            platform_values.append("iOS")
            platform_evidence.extend(f"{prefix}:{item}" for item in result.evidence)

            xcode_markers = {".xcodeproj", ".xcworkspace"}
            if evidence & xcode_markers:
                framework_values.append("iOS Native")
                framework_evidence.extend(
                    f"{prefix}:{item}"
                    for item in result.evidence
                    if item in xcode_markers
                )
                toolchain_values.append("Xcode")
                toolchain_evidence.extend(
                    f"{prefix}:{item}"
                    for item in result.evidence
                    if item in xcode_markers
                )

            if "Package.swift" in evidence:
                toolchain_values.append("Swift Package Manager")
                toolchain_evidence.append(f"{prefix}:Package.swift")

            if "source:swift" in evidence:
                language_values.append("Swift")
                language_evidence.append(f"{prefix}:source:swift")
            if "source:objc" in evidence:
                language_values.append("Objective-C")
                language_evidence.append(f"{prefix}:source:objc")

        elif result.profile_id == "react-native":
            framework_values.append("React Native")
            framework_evidence.extend(f"{prefix}:{item}" for item in result.evidence)

            if "package.json:react-native" in evidence or "package.json" in evidence:
                toolchain_values.append("Node.js")
                toolchain_evidence.extend(
                    f"{prefix}:{item}"
                    for item in result.evidence
                    if item in {"package.json:react-native", "package.json"}
                )

            if "source:typescript" in evidence or "source:tsx" in evidence:
                language_values.append("TypeScript")
                language_evidence.extend(
                    f"{prefix}:{item}"
                    for item in result.evidence
                    if item in {"source:typescript", "source:tsx"}
                )
            if "source:javascript" in evidence or "source:jsx" in evidence:
                language_values.append("JavaScript")
                language_evidence.extend(
                    f"{prefix}:{item}"
                    for item in result.evidence
                    if item in {"source:javascript", "source:jsx"}
                )

    platform_values = list(dict.fromkeys(platform_values))
    framework_values = list(dict.fromkeys(framework_values))
    language_values = list(dict.fromkeys(language_values))
    toolchain_values = list(dict.fromkeys(toolchain_values))

    reasons: list[str] = []
    ambiguous = False

    if len(platform_values) > 1:
        ambiguous = True
        reasons.append("multiple platforms detected")
    if "React Native" in framework_values and not platform_values:
        ambiguous = True
        reasons.append("React Native detected without an explicit native platform")

    families = {
        "JVM" if value in {"Kotlin", "Java"} else
        "Apple" if value in {"Swift", "Objective-C"} else
        "JavaScript" if value in {"TypeScript", "JavaScript"} else
        value
        for value in language_values
    }
    if len(families) > 1:
        ambiguous = True
        reasons.append("multiple language families detected")

    platform_confidence = (
        top_confidence if len(platform_values) == 1
        else min((item.confidence for item in detections), default=0.0)
    )
    framework_confidence = 1.0 if framework_values and framework_evidence else 0.0
    values = tuple(dict.fromkeys(language_values + toolchain_values))
    evidence = tuple(language_evidence + toolchain_evidence)
    language_toolchain_confidence = 1.0 if values and evidence else 0.0

    return ProjectClassification(
        platform=ClassificationDimension(
            "Platform", tuple(platform_values), platform_confidence, tuple(platform_evidence)
        ),
        framework_runtime=ClassificationDimension(
            "Framework / Runtime", tuple(framework_values), framework_confidence, tuple(framework_evidence)
        ),
        language_toolchain=ClassificationDimension(
            "Language / Toolchain", values, language_toolchain_confidence, evidence
        ),
        ambiguous=ambiguous,
        reasons=tuple(reasons),
    )
