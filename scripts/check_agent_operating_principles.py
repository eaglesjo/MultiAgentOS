#!/usr/bin/env python3
"""Validate the repository-wide agent operating-principles contract.

This guards the policy's required entry point and minimum control coverage. It
does not claim to enforce agent behavior at runtime; that requires separate
runtime/tooling controls.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
PRINCIPLES = ROOT / "docs" / "AGENT_OPERATING_PRINCIPLES.md"

REQUIRED_AGENT_ENTRYPOINT = "[Agent Operating Principles](docs/AGENT_OPERATING_PRINCIPLES.md)"
REQUIRED_HEADINGS = (
    "# Agent Operating Principles",
    "## Required behavior",
    "## Minimum completion checklist",
    "## Tool limitation handling",
    "## Scope",
)
REQUIRED_PRINCIPLES = (
    "Execute directly when authorized and capable.",
    "Verify actual state after every meaningful action.",
    "Be explicit about capability and permission limits.",
    "Include cleanup in the plan.",
    "Report evidence, not assumptions.",
    "Respect authorization and safety boundaries.",
    "Plan for completion.",
)
REQUIRED_CHECKLIST_ITEMS = (
    "Requested change exists in the intended repository, branch, or environment.",
    "Diff and resulting state have been inspected.",
    "Relevant tests, CI checks, or runtime probes have been checked",
    "Temporary resources have been cleaned up",
    "Final report links to the relevant commit, PR, run, or resource",
)


def main() -> int:
    errors: list[str] = []
    if not AGENTS.is_file():
        errors.append("Missing repository entry-point instructions: AGENTS.md")
        agents_text = ""
    else:
        agents_text = AGENTS.read_text(encoding="utf-8")

    if not PRINCIPLES.is_file():
        errors.append("Missing policy document: docs/AGENT_OPERATING_PRINCIPLES.md")
        policy_text = ""
    else:
        policy_text = PRINCIPLES.read_text(encoding="utf-8")

    if REQUIRED_AGENT_ENTRYPOINT not in agents_text:
        errors.append("AGENTS.md must link to the canonical agent operating-principles document.")

    for heading in REQUIRED_HEADINGS:
        if heading not in policy_text:
            errors.append(f"Policy document is missing required section: {heading}")

    for principle in REQUIRED_PRINCIPLES:
        if principle not in policy_text:
            errors.append(f"Policy document is missing required principle: {principle}")

    for item in REQUIRED_CHECKLIST_ITEMS:
        if item not in policy_text:
            errors.append(f"Policy document is missing a completion-checklist requirement containing: {item}")

    if errors:
        print("Agent operating-principles contract: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Agent operating-principles contract: PASS")
    print(f"Validated entry point: {AGENTS.relative_to(ROOT)}")
    print(f"Validated policy: {PRINCIPLES.relative_to(ROOT)}")
    print(f"Required principles: {len(REQUIRED_PRINCIPLES)}")
    print(f"Required completion-checklist items: {len(REQUIRED_CHECKLIST_ITEMS)}")
    print("Note: this check protects policy-document coverage; it does not enforce runtime behavior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
