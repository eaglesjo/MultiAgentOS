"""Additional development specialist definitions.

These roles cover common software-delivery responsibilities beyond the
platform-specific frontend/mobile specialists.
"""

from core.contracts.agent import AgentTaxonomy


_DEVELOPMENT_SPECIALISTS = {
    "software-architect": (
        {"architecture", "design"},
        {"filesystem.read"},
        AgentTaxonomy(
            domain="development",
            specialization="architecture",
            parent_id="development",
        ),
    ),
    "backend-developer": (
        {"code", "backend"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="development",
            specialization="backend",
            parent_id="development",
        ),
    ),
    "api-developer": (
        {"code", "api"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="development",
            specialization="api",
            parent_id="development",
        ),
    ),
    "database-engineer": (
        {"database", "data"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="development",
            specialization="database",
            parent_id="development",
        ),
    ),
    "ux-designer": (
        {"ux", "design", "research"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="ui",
            specialization="ux",
            parent_id="ui-agent",
        ),
    ),
    "ui-designer": (
        {"ui", "design", "visual"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="ui",
            specialization="design",
            parent_id="ui-agent",
        ),
    ),
    "design-system-specialist": (
        {"design-system", "ui"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="ui",
            specialization="design-system",
            parent_id="ui-agent",
        ),
    ),
    "accessibility-specialist": (
        {"accessibility", "ui", "quality"},
        {"filesystem.read", "filesystem.write"},
        AgentTaxonomy(
            domain="ui",
            specialization="accessibility",
            parent_id="ui-agent",
        ),
    ),
    "qa-engineer": (
        {"testing", "quality"},
        {"filesystem.read", "process"},
        AgentTaxonomy(
            domain="testing",
            specialization="qa",
        ),
    ),
    "security-engineer": (
        {"security", "quality"},
        {"filesystem.read", "process"},
        AgentTaxonomy(
            domain="quality",
            specialization="security",
        ),
    ),
    "performance-engineer": (
        {"performance", "quality"},
        {"filesystem.read", "process"},
        AgentTaxonomy(
            domain="quality",
            specialization="performance",
        ),
    ),
    "devops-engineer": (
        {"build", "deployment", "operations"},
        {"filesystem.read", "filesystem.write", "process"},
        AgentTaxonomy(
            domain="operations",
            specialization="devops",
        ),
    ),
}
