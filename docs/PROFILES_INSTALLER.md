# VYRELON Profiles and Installer

VYRELON profiles describe technology environments, not product domains.

Built-in profiles:

- React Native
- Android Native
- iOS Native

Common roles are shared across profiles, while technology-specific roles extend them.

## Detection

Profile detection is evidence-based. It inspects repository files and known technology markers rather than asking an AI to guess the project type.

Multiple profiles can be detected. This is intentional for projects such as React Native repositories that contain both Android and iOS native projects.

## Initialization

ProjectInitializer applies a small, non-secret bootstrap file:

    .multiagentos/profile.json

The file records detected profiles and evidence. It does not contain credentials or provider API keys.

Domain-specific agents belong in the target project or a separate domain profile; they are not placed into the generic technology profiles.
