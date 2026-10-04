import unittest

from agents.catalog import build_agent_catalog


class AgentCatalogTests(unittest.TestCase):
    def test_governance_roles_are_not_duplicated_as_specialists(self):
        agents = {agent.id: agent for agent in build_agent_catalog()}

        for agent_id in (
            "planner",
            "editor",
            "executor",
            "reviewer",
            "debugger",
        ):
            self.assertEqual(agents[agent_id].kind, "governance")
            self.assertEqual(agents[agent_id].taxonomy.layer, "governance")

    def test_researcher_and_tester_are_explicit_specialists(self):
        agents = {agent.id: agent for agent in build_agent_catalog()}

        self.assertEqual(agents["researcher"].kind, "specialist")
        self.assertEqual(agents["researcher"].taxonomy.domain, "research")
        self.assertEqual(agents["researcher"].taxonomy.specialization, "general")

        self.assertEqual(agents["tester"].kind, "specialist")
        self.assertEqual(agents["tester"].taxonomy.domain, "testing")
        self.assertEqual(agents["tester"].taxonomy.specialization, "general")


    def test_agent_contract_rejects_kind_taxonomy_mismatch(self):
        from core.contracts.agent import AgentContract, AgentTaxonomy

        governance = AgentContract(
            id="invalid-governance",
            role="invalid-governance",
            kind="governance",
            taxonomy=AgentTaxonomy(),
        )
        with self.assertRaises(ValueError):
            governance.validate()

        specialist = AgentContract(
            id="invalid-specialist",
            role="invalid-specialist",
            kind="specialist",
            taxonomy=AgentTaxonomy(layer="governance"),
        )
        with self.assertRaises(ValueError):
            specialist.validate()

    def test_catalog_contracts_validate(self):
        for agent in build_agent_catalog():
            agent.validate()

    def test_governance_and_specialist_layers_are_disjoint_by_id(self):
        agents = build_agent_catalog()

        governance_ids = {
            agent.id for agent in agents if agent.taxonomy.layer == "governance"
        }
        specialist_ids = {
            agent.id for agent in agents if agent.taxonomy.layer == "specialist"
        }

        self.assertTrue(governance_ids)
        self.assertTrue(specialist_ids)
        self.assertTrue(governance_ids.isdisjoint(specialist_ids))


if __name__ == "__main__":
    unittest.main()
