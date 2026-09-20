"""Built-in VYRELON technology profile registry."""

from core.contracts.profile import ProfileSpec
from profiles.common import COMMON_ROLES


PROFILES = (
    ProfileSpec(
        id="react-native",
        display_name="React Native",
        detect_files=frozenset({"package.json"}),
        detect_markers=frozenset({"react-native"}),
        roles=COMMON_ROLES + (
            "architect", "developer", "ui", "navigation", "state-management",
        ),
    ),
    ProfileSpec(
        id="android-native",
        display_name="Android Native",
        detect_files=frozenset({"settings.gradle", "settings.gradle.kts"}),
        detect_markers=frozenset({"com.android.application", "com.android.library"}),
        roles=COMMON_ROLES + (
            "android-architect", "kotlin-developer", "jetpack-compose", "gradle",
        ),
    ),
    ProfileSpec(
        id="ios-native",
        display_name="iOS Native",
        detect_files=frozenset({"Package.swift"}),
        detect_markers=frozenset({".xcodeproj", ".xcworkspace"}),
        roles=COMMON_ROLES + (
            "ios-architect", "swift-developer", "swiftui", "xcode",
        ),
    ),
)


class ProfileRegistry:
    def __init__(self, profiles: tuple[ProfileSpec, ...] = PROFILES) -> None:
        self._profiles = {profile.id: profile for profile in profiles}

    def get(self, profile_id: str) -> ProfileSpec:
        return self._profiles[profile_id]

    def list(self) -> tuple[ProfileSpec, ...]:
        return tuple(self._profiles.values())
