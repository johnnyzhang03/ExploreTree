import asyncio
import unittest

from app.sessions import (
    ExplorationSession,
    SessionManager,
    SessionNotFoundError,
)


class ExplorationSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscriber_receives_backlog_then_live_events(self) -> None:
        session = ExplorationSession(id="session", question="question")
        first = {"type": "planning"}
        second = {"type": "done"}

        await session.publish(first)
        backlog, queue = await session.subscribe()
        await session.publish(second)

        self.assertEqual(backlog, [first])
        self.assertEqual(await asyncio.wait_for(queue.get(), timeout=1), second)
        await session.unsubscribe(queue)
        self.assertEqual(session.subscribers, set())

    async def test_session_completes_after_all_operations_finish(self) -> None:
        session = ExplorationSession(id="session", question="question")

        session.begin_operation()
        session.begin_operation()
        await session.finish_operation()

        self.assertEqual(session.status, "running")
        await session.finish_operation()
        self.assertEqual(session.status, "completed")

    async def test_snapshot_contains_default_research_brief(self) -> None:
        session = ExplorationSession(id="session", question="question")

        self.assertEqual(
            session.snapshot()["brief"],
            {
                "question": "question",
                "objective": "",
                "audience": "",
                "scope": [],
                "constraints": [],
                "freshness": "",
                "desiredOutput": "",
            },
        )

    async def test_artifact_contains_compact_sourced_findings(self) -> None:
        session = ExplorationSession(id="session", question="question")
        node = session.tree.add(
            label="Market economics",
            parent_id="root",
            status="done",
            depth=1,
            verticals=["web", "finance"],
        )
        node.insight = "Margins depend on rent and customer volume."
        node.sources = [
            {
                "title": "Market report",
                "url": "https://example.com/report",
            },
            {
                "title": "Secondary report",
                "url": "https://example.com/secondary",
            },
        ]
        session.begin_operation()
        await session.finish_operation()

        artifact = session.artifact()

        self.assertEqual(artifact["status"], "completed")
        self.assertEqual(artifact["sessionId"], "session")
        self.assertEqual(len(artifact["keyFindings"][0]["sources"]), 1)
        self.assertEqual(
            artifact["coverage"]["verticals"],
            ["finance", "web"],
        )


class SessionManagerTests(unittest.TestCase):
    def test_unknown_session_raises_specific_error(self) -> None:
        manager = SessionManager()

        with self.assertRaises(SessionNotFoundError):
            manager.get("missing")
