"""Built-in specialist agent definitions."""

from core.contracts.agent import AgentContract

_COMMON = {
    "planner": ({"planning"}, {"filesystem.read"}),
    "researcher": ({"research"}, {"network.read"}),
    "editor": ({"editing"}, {"filesystem.read", "filesystem.write"}),
    "executor": ({"execution"}, {"filesystem.read", "filesystem.write", "process"}),
    "tester": ({"testing"}, {"filesystem.read", "process"}),
    "debugger": ({"debugging"}, {"filesystem.read", "process"}),
    "reviewer": ({"review"}, {"filesystem.read"}),
}

_PROFILE_SPECIALISTS = {
    "react-native": {
        "architect": ({"architecture", "react-native"}, {"filesystem.read"}),
        "developer": ({"code", "react-native"}, {"filesystem.read", "filesystem.write"}),
        "ui": ({"ui", "react-native"}, {"filesystem.read", "filesystem.write"}),
        "navigation": ({"navigation", "react-native"}, {"filesystem.read", "filesystem.write"}),
        "state-management": ({"state-management", "react-native"}, {"filesystem.read", "filesystem.write"}),
    },
    "android-native": {
        "android-architect": ({"architecture", "android"}, {"filesystem.read"}),
        "kotlin-developer": ({"code", "kotlin"}, {"filesystem.read", "filesystem.write"}),
        "jetpack-compose": ({"ui", "compose", "kotlin"}, {"filesystem.read", "filesystem.write"}),
        "gradle": ({"build", "gradle"}, {"filesystem.read", "filesystem.write", "process"}),
    },
    "ios-native": {
        "ios-architect": ({"architecture", "ios"}, {"filesystem.read"}),
        "swift-developer": ({"code", "swift"}, {"filesystem.read", "filesystem.write"}),
        "swiftui": ({"ui", "swiftui"}, {"filesystem.read", "filesystem.write"}),
        "xcode": ({"build", "xcode"}, {"filesystem.read", "filesystem.write", "process"}),
    },
}


def build_agent_catalog(profile_ids: tuple[str, ...] = ()) -> tuple[AgentContract, ...]:
    definitions: dict[str, tuple[set[str], set[str]]] = dict(_COMMON)
    for profile_id in profile_ids:
        definitions.update(_PROFILE_SPECIALISTS.get(profile_id, {}))
    return tuple(
        AgentContract(
            id=agent_id,
            role=agent_id,
            capabilities=frozenset(capabilities),
            tools=frozenset(tools),
            metadata={"profiles": list(profile_ids)},
            kind="specialist",
        )
        for agent_id, (capabilities, tools) in sorted(definitions.items())
    )
