"""Environment-based credential validation for model providers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CredentialCheck:
    """Non-secret result of checking one environment-backed credential."""

    environment_variable: str
    present: bool


class EnvironmentCredentialResolver:
    """Resolve credentials from environment variables without persisting secrets."""

    def resolve(self, environment_variable: str) -> str:
        value = os.environ.get(environment_variable)
        if not value:
            raise RuntimeError(
                f"Required model credential environment variable is missing: "
                f"{environment_variable}"
            )
        return value

    def check(self, environment_variables: list[str]) -> tuple[CredentialCheck, ...]:
        return tuple(
            CredentialCheck(
                environment_variable=name,
                present=bool(os.environ.get(name)),
            )
            for name in environment_variables
        )

    def check_mapping(
        self, header_env: Mapping[str, str]
    ) -> tuple[CredentialCheck, ...]:
        return self.check(list(header_env.values()))
