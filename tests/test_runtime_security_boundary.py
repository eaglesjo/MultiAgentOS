import unittest

from core.contracts.idempotency import IdempotencyContract, IdempotencyMode
from core.security import redact_sensitive


class RuntimeSecurityBoundaryTests(unittest.TestCase):
    def test_sensitive_keys_are_redacted(self):
        payload = {
            "api_key": "super-secret",
            "nested": {"password": "hunter2"},
            "safe": "ordinary value",
        }
        result = redact_sensitive(payload)
        self.assertEqual(result["api_key"], "[REDACTED]")
        self.assertEqual(result["nested"]["password"], "[REDACTED]")
        self.assertEqual(result["safe"], "ordinary value")

    def test_known_token_patterns_are_redacted(self):
        value = "Bearer abcdefghijklmnop and sk-abcdefghijklmnop"
        result = redact_sensitive(value)
        self.assertNotIn("abcdefghijklmnop", result)
        self.assertEqual(result.count("[REDACTED]"), 2)

    def test_keyed_idempotency_requires_key(self):
        self.assertTrue(IdempotencyContract(IdempotencyMode.KEYED, "work-1:call-1").replay_safe)
        with self.assertRaises(ValueError):
            IdempotencyContract(IdempotencyMode.KEYED)

    def test_none_idempotency_is_not_replay_safe(self):
        self.assertFalse(IdempotencyContract(IdempotencyMode.NONE).replay_safe)


if __name__ == "__main__":
    unittest.main()
