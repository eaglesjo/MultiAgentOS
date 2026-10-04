"""Built-in governance and specialist agent definitions."""

from core.contracts.agent import AgentContract, AgentTaxonomy


# These are intentionally specialist roles. Governance roles are defined below
# and must not be duplicated here: planner/editor/executor/reviewer/debugger
# are governance agents, while researcher/tester remain reusable specialists.
_COMMON_SPECIALISTS = {
    "researcher": (
        {"research"},
        {"network.read"},
        AgentTaxonomy(domain="research", specialization="general"),
    ),
    "tester": (
        {"testing"},
        {"filesystem.read", "process"},
        AgentTaxonomy(domain="testing", specialization="general"),
    ),
}


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


# Development specialists are deliberately platform-oriented. React means
# browser/web React; React Native is kept as its own cross-platform target.
_DEVELOPMENT_SPECIALISTS = {
    "react-developer": (
        {"code", "react", "web"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="development",
            platform="web",
            technology="react",
            parent_id="development",
        ),
    ),
    "react-native-developer": (
        {"code", "react-native"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="development",
            platform="react-native",
            technology="react-native",
            parent_id="development",
        ),
    ),
    "android-developer": (
        {"code", "android", "kotlin"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="development",
            platform="android",
            technology="kotlin",
            parent_id="development",
        ),
    ),
    "ios-developer": (
        {"code", "ios", "swift"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="development",
            platform="ios",
            technology="swift",
            parent_id="development",
        ),
    ),
}


# UI specialists form an explicit hierarchy: UI -> Web / Cross-platform /
# Native -> Android / iOS. Browser Agent remains a capability, not the UI root.
_UI_SPECIALISTS = {
    "ui-agent": (
        {"ui", "routing"},
        {"filesystem.read"},
        AgentTaxonomy(domain="ui"),
    ),
    "ui-web": (
        {"ui", "web"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(domain="ui", platform="web", parent_id="ui-agent"),
    ),
    "ui-react-native": (
        {"ui", "react-native"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="ui",
            platform="react-native",
            technology="react-native",
            parent_id="ui-agent",
        ),
    ),
    "ui-native": (
        {"ui", "native"},
        {"filesystem.read"},
        AgentTaxonomy(domain="ui", platform="native", parent_id="ui-agent"),
    ),
    "ui-android": (
        {"ui", "android", "compose"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="ui",
            platform="android",
            technology="jetpack-compose",
            parent_id="ui-native",
        ),
    ),
    "ui-ios": (
        {"ui", "ios", "swiftui"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="ui",
            platform="ios",
            technology="swiftui",
            parent_id="ui-native",
        ),
    ),
}


_RESEARCH_SPECIALISTS = {
    "development-research-react": (
        {"research", "development-research", "react"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(
            domain="research",
            platform="web",
            technology="react",
            specialization="development",
            parent_id="development-research",
        ),
    ),
    "development-research-react-native": (
        {"research", "development-research", "react-native"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(
            domain="research",
            platform="react-native",
            technology="react-native",
            specialization="development",
            parent_id="development-research",
        ),
    ),
    "development-research-android": (
        {"research", "development-research", "android"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(
            domain="research",
            platform="android",
            technology="android",
            specialization="development",
            parent_id="development-research",
        ),
    ),
    "development-research-ios": (
        {"research", "development-research", "ios"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(
            domain="research",
            platform="ios",
            technology="ios",
            specialization="development",
            parent_id="development-research",
        ),
    ),
    "ui-research-web": (
        {"research", "ui-research", "web"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(
            domain="research",
            platform="web",
            technology="react",
            specialization="ui",
            parent_id="ui-research",
        ),
    ),
    "ui-research-react-native": (
        {"research", "ui-research", "react-native"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(
            domain="research",
            platform="react-native",
            technology="react-native",
            specialization="ui",
            parent_id="ui-research",
        ),
    ),
    "ui-research-android": (
        {"research", "ui-research", "android"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(
            domain="research",
            platform="android",
            technology="jetpack-compose",
            specialization="ui",
            parent_id="ui-research",
        ),
    ),
    "ui-research-ios": (
        {"research", "ui-research", "ios"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(
            domain="research",
            platform="ios",
            technology="swiftui",
            specialization="ui",
            parent_id="ui-research",
        ),
    ),
}


_ROUTING_NODES = {
    "development": (
        {"development", "routing"},
        {"filesystem.read"},
        AgentTaxonomy(domain="development"),
    ),
    "development-research": (
        {"research", "development-research", "routing"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(domain="research", specialization="development"),
    ),
    "ui-research": (
        {"research", "ui-research", "routing"},
        {"network.read", "filesystem.read"},
        AgentTaxonomy(domain="research", specialization="ui"),
    ),
}


def _build_definition_map() -> dict[str, tuple[set[str], set[str], AgentTaxonomy]]:
    definitions: dict[str, tuple[set[str], set[str], AgentTaxonomy]] = {}
    for agent_id, (capabilities, tools, taxonomy) in _COMMON_SPECIALISTS.items():
        definitions[agent_id] = (capabilities, tools, taxonomy)
    for agent_id, (capabilities, tools, taxonomy) in _GOVERNANCE_ROLES.items():
        definitions[agent_id] = (
            capabilities,
            tools,
            AgentTaxonomy(layer="governance"),
        )
    definitions.update(_DEVELOPMENT_SPECIALISTS)
    definitions.update(_UI_SPECIALISTS)
    definitions.update(_RESEARCH_SPECIALISTS)
    definitions.update(_ROUTING_NODES)
    return definitions


def build_agent_catalog(profile_ids: tuple[str, ...] = ()) -> tuple[AgentContract, ...]:
    """Build the complete catalog without coupling agents to an AI vendor."""
    definitions = _build_definition_map()

    # Preserve the existing profile-specialist catalog for compatibility while
    # exposing the new platform-oriented development/UI taxonomy.
    profile_specialists = {
        "react-native": {
            "architect": (
                {"architecture", "react-native"},
                {"filesystem.read"},
                AgentTaxonomy(domain="development", platform="react-native", technology="react-native"),
            ),
            "developer": (
                {"code", "react-native"},
                {"filesystem.read", "filesystem.write"},
                AgentTaxonomy(domain="development", platform="react-native", technology="react-native"),
            ),
            "ui": (
                {"ui", "react-native"},
                {"filesystem.read", "filesystem.write"},
                AgentTaxonomy(domain="ui", platform="react-native", technology="react-native"),
            ),
            "navigation": (
                {"navigation", "react-native"},
                {"filesystem.read", "filesystem.write"},
                AgentTaxonomy(domain="ui", platform="react-native", technology="navigation"),
            ),
            "state-management": (
                {"state-management", "react-native"},
                {"filesystem.read", "filesystem.write"},
                AgentTaxonomy(domain="development", platform="react-native", technology="state-management"),
            ),
        },
        "android-native": {
            "android-architect": (
                {"architecture", "android"},
                {"filesystem.read"},
                AgentTaxonomy(domain="development", platform="android", technology="architecture"),
            ),
            "kotlin-developer": (
                {"code", "kotlin"},
                {"filesystem.read", "filesystem.write"},
                AgentTaxonomy(domain="development", platform="android", technology="kotlin"),
            ),
            "jetpack-compose": (
                {"ui", "compose", "kotlin"},
                {"filesystem.read", "filesystem.write"},
                AgentTaxonomy(domain="ui", platform="android", technology="jetpack-compose"),
            ),
            "gradle": (
                {"build", "gradle"},
                {"filesystem.read", "filesystem.write", "process"},
                AgentTaxonomy(domain="development", platform="android", technology="gradle"),
            ),
        },
        "ios-native": {
            "ios-architect": (
                {"architecture", "ios"},
                {"filesystem.read"},
                AgentTaxonomy(domain="development", platform="ios", technology="architecture"),
            ),
            "swift-developer": (
                {"code", "swift"},
                {"filesystem.read", "filesystem.write"},
                AgentTaxonomy(domain="development", platform="ios", technology="swift"),
            ),
            "swiftui": (
                {"ui", "swiftui"},
                {"filesystem.read", "filesystem.write"},
                AgentTaxonomy(domain="ui", platform="ios", technology="swiftui"),
            ),
            "xcode": (
                {"build", "xcode"},
                {"filesystem.read", "filesystem.write", "process"},
                AgentTaxonomy(domain="development", platform="ios", technology="xcode"),
            ),
        },
    }

    for profile_id in profile_ids:
        for agent_id, definition in profile_specialists.get(profile_id, {}).items():
            definitions[agent_id] = definition

    agents = []
    for agent_id, (capabilities, tools, taxonomy) in sorted(definitions.items()):
        governance = _GOVERNANCE_ROLES.get(agent_id)
        permissions = governance[2] if governance else frozenset(tools)
        metadata = {
            "profiles": list(profile_ids),
            "taxonomy": {
                "layer": taxonomy.layer,
                "domain": taxonomy.domain,
                "platform": taxonomy.platform,
                "technology": taxonomy.technology,
                "specialization": taxonomy.specialization,
                "parent_id": taxonomy.parent_id,
            },
        }
        if governance:
            metadata.update({
                "execution_role": True,
                "governance_source": "MultiAgentOS",
            })
        agents.append(
            AgentContract(
                id=agent_id,
                role=agent_id,
                capabilities=frozenset(capabilities),
                tools=frozenset(tools),
                permissions=permissions,
                metadata=metadata,
                kind="governance" if governance else "specialist",
                scope_aware=True,
                taxonomy=taxonomy,
            )
        )
    return tuple(agents)
