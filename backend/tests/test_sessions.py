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


class SessionManagerTests(unittest.TestCase):
    def test_unknown_session_raises_specific_error(self) -> None:
        manager = SessionManager()

        with self.assertRaises(SessionNotFoundError):
            manager.get("missing")
