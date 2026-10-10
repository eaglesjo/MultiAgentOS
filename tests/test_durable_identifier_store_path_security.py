"""Regression tests for traversal in artifact, approval, and chat-session stores."""

import tempfile
import unittest
from pathlib import Path

from core.approval import ApprovalStore
from core.artifacts import ArtifactStore
from core.chat_session import ChatSession, ChatSessionStore
from core.contracts.approval import ApprovalDecision, ApprovalGrant
from core.contracts.handoff import ArtifactContract


class DurableIdentifierStorePathSecurityTests(unittest.TestCase):
    INVALID_IDS = ("../outside", r"..\\outside", "bad:stream", "", ".", "..", "bad\x00id")

    def test_load_and_write_reject_invalid_identifiers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifacts = ArtifactStore(root / "artifacts")
            approvals = ApprovalStore(root / "approvals")
            sessions = ChatSessionStore(root / "sessions")

            for identifier in self.INVALID_IDS:
                with self.subTest(store="artifact", identifier=repr(identifier)):
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        artifacts.load(identifier)
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        artifacts.save(ArtifactContract(
                            id=identifier,
                            kind="report",
                            producer_agent_id="agent-1",
                            content_ref="memory://artifact",
                        ))

                with self.subTest(store="approval", identifier=repr(identifier)):
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        approvals.load(identifier)
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        approvals.save(ApprovalGrant(
                            approval_id=identifier,
                            decision=ApprovalDecision.DENIED,
                            action="git.push",
                        ))

                with self.subTest(store="chat-session", identifier=repr(identifier)):
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        sessions.load(identifier)
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        sessions.save(ChatSession(
                            id=identifier,
                            chat_agent_id="chat-agent-1",
                        ))

    def test_all_stores_reject_symlink_escape_for_read_and_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside.json"
            outside.write_text('{"sentinel":"unchanged"}\n', encoding="utf-8")
            artifact_root = root / "artifacts"
            approval_root = root / "approvals"
            session_root = root / "sessions"
            for directory in (artifact_root, approval_root, session_root):
                directory.mkdir()

            links = (
                artifact_root / "item-1.json",
                approval_root / "grant-1.json",
                session_root / "session-1.json",
            )
            try:
                for link in links:
                    link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")

            artifacts = ArtifactStore(artifact_root)
            approvals = ApprovalStore(approval_root)
            sessions = ChatSessionStore(session_root)

            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                artifacts.load("item-1")
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                artifacts.save(ArtifactContract(
                    id="item-1", kind="report", producer_agent_id="agent-1",
                    content_ref="memory://artifact",
                ))
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                approvals.load("grant-1")
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                approvals.save(ApprovalGrant(
                    approval_id="grant-1", decision=ApprovalDecision.DENIED,
                    action="git.push",
                ))
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                sessions.load("session-1")
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                sessions.save(ChatSession(id="session-1", chat_agent_id="chat-agent-1"))

            self.assertEqual(outside.read_text(encoding="utf-8"), '{"sentinel":"unchanged"}\n')


if __name__ == "__main__":
    unittest.main()
