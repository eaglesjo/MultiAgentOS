"""Installation components for VYRELON and its optional multi-agent layer."""

from __future__ import annotations

from dataclasses import dataclass

VYRELON = "vyrelon"
MULTI_AGENT = "multi-agent"
ALL = "all"

VALID_COMPONENTS = frozenset({VYRELON, MULTI_AGENT, ALL})


@dataclass(frozen=True)
class Installation:
    components: frozenset[str]

    @property
    def has_vyrelon(self) -> bool:
        return VYRELON in self.components

    @property
    def has_multi_agent(self) -> bool:
        return MULTI_AGENT in self.components

    def as_payload(self) -> dict[str, object]:
        return {
            "version": 1,
            "components": sorted(self.components),
            "features": {
                "github": self.has_vyrelon,
                "local_runtime": self.has_vyrelon,
                "multi_agent": self.has_multi_agent,
            },
        }


def normalize_component(component: str) -> str:
    value = component.strip().lower()
    if value not in VALID_COMPONENTS:
        raise ValueError(
            f"Unknown component {component!r}; expected vyrelon, multi-agent, or all"
        )
    if value == ALL:
        return ALL
    return value


def resolve_installation(component: str) -> Installation:
    value = normalize_component(component)
    if value == ALL:
        return Installation(frozenset({VYRELON, MULTI_AGENT}))
    return Installation(frozenset({value}))
