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

    async def test_completion_handoff_can_only_be_claimed_once(self) -> None:
        session = ExplorationSession(id="session", question="question")

        claims = await asyncio.gather(
            session.claim_completion_handoff(),
            session.claim_completion_handoff(),
        )

        self.assertEqual(sorted(claims), [False, True])
        await session.release_completion_handoff()
        self.assertTrue(await session.claim_completion_handoff())

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
                "domain": "example.com",
                "vertical": "web",
                "publishedAt": "2026-07-20",
            },
            {
                "title": "Secondary report",
                "url": "https://analysis.test/secondary",
                "domain": "analysis.test",
                "vertical": "finance",
                "publishedAt": "2026-07-20",
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
        self.assertEqual(artifact["coverage"]["evidence"]["sourceCount"], 2)
        self.assertEqual(artifact["coverage"]["evidence"]["domainCount"], 2)
        self.assertEqual(artifact["coverage"]["evidence"]["datedSourceCount"], 2)
        self.assertEqual(
            artifact["keyFindings"][0]["evidenceCoverage"]["dateRange"],
            {"oldest": "2026-07-20", "newest": "2026-07-20"},
        )
        self.assertEqual(artifact["treeOutline"][0]["nodeId"], node.id)

    async def test_tree_outline_contains_branch_metadata(self) -> None:
        session = ExplorationSession(id="session", question="question")
        root = session.tree.add("Question", None, status="done", depth=0)
        child = session.tree.add(
            "Regulatory risk",
            root.id,
            status="done",
            depth=1,
        )
        child.insight = "Licensing requirements vary by market."
        child.sources = [{"url": "https://example.com/rules"}]

        outline = session.tree_outline()

        item = next(node for node in outline["nodes"] if node["nodeId"] == child.id)
        self.assertEqual(item["path"], ["Question", "Regulatory risk"])
        self.assertEqual(item["evidenceCount"], 1)
        self.assertTrue(item["evidenceCoverage"]["gaps"]["singleSource"])
        self.assertEqual(item["childCount"], 0)

    async def test_branch_context_returns_selected_subtree(self) -> None:
        session = ExplorationSession(id="session", question="question")
        root = session.tree.add("Question", None, status="done", depth=0)
        branch = session.tree.add("Market", root.id, status="done", depth=1)
        child = session.tree.add("Demand", branch.id, status="done", depth=2)
        child.insight = "Demand is increasing."

        context = session.branch_context([branch.id])

        self.assertEqual(context["branches"][0]["nodeId"], branch.id)
        self.assertEqual(
            [item["nodeId"] for item in context["branches"][0]["findings"]],
            [branch.id, child.id],
        )


class SessionManagerTests(unittest.TestCase):
    def test_unknown_session_raises_specific_error(self) -> None:
        manager = SessionManager()

        with self.assertRaises(SessionNotFoundError):
            manager.get("missing")
