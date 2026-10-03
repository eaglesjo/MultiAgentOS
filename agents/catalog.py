"""Built-in specialist and governance execution-role definitions."""

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

# PetTarotReading execution roles are represented as native AgentContract
# entries. They do not introduce a second orchestration/runtime layer.
_GOVERNANCE_ROLES = {
    "file-picker": (
        {"discovery"},
        {"filesystem.read"},
        frozenset({"filesystem.read"}),
    ),
    "planner": (
        {"planning", "scope"},
        {"filesystem.read"},
        frozenset({"filesystem.read"}),
    ),
    "web-researcher": (
        {"research"},
        {"network.read"},
        frozenset({"network.read"}),
    ),
    "editor": (
        {"editing", "scope-aware"},
        {"filesystem.read", "filesystem.write"},
        frozenset({"filesystem.read", "filesystem.write"}),
    ),
    "executor": (
        {"execution", "validation"},
        {"filesystem.read", "filesystem.write", "process"},
        frozenset({"filesystem.read", "filesystem.write", "process"}),
    ),
    "terminal-monitor": (
        {"monitoring"},
        {"process.read"},
        frozenset({"process.read"}),
    ),
    "reviewer": (
        {"review", "evidence"},
        {"filesystem.read"},
        frozenset({"filesystem.read"}),
    ),
    "browser-agent": (
        {"browser-validation"},
        {"browser"},
        frozenset({"browser"}),
    ),
    "debugger": (
        {"debugging", "scope-aware"},
        {"filesystem.read", "filesystem.write", "process"},
        frozenset({"filesystem.read", "filesystem.write", "process"}),
    ),
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
    definitions.update(
        {agent_id: (capabilities, tools) for agent_id, (capabilities, tools, _) in _GOVERNANCE_ROLES.items()}
    )
    for profile_id in profile_ids:
        definitions.update(_PROFILE_SPECIALISTS.get(profile_id, {}))

    agents = []
    for agent_id, (capabilities, tools) in sorted(definitions.items()):
        governance = _GOVERNANCE_ROLES.get(agent_id)
        permissions = governance[2] if governance else frozenset(tools)
        metadata = {"profiles": list(profile_ids)}
        if governance:
            metadata.update({
                "execution_role": True,
                "governance_source": "PetTarotReading",
            })
        agents.append(
            AgentContract(
                id=agent_id,
                role=agent_id,
                capabilities=frozenset(capabilities),
                tools=frozenset(tools),
                permissions=permissions,
                metadata=metadata,
                kind="specialist",
                scope_aware=True,
            )
        )
    return tuple(agents)
