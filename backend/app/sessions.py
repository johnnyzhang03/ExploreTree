"""Exploration sessions shared by MCP tools and WebSocket clients."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .agent import add_followup, expand_on_demand, explore, get_media
from .config import settings
from .research_brief import ResearchBrief
from .tree import Tree

logger = logging.getLogger(__name__)


class SessionNotFoundError(KeyError):
    pass


@dataclass
class ExplorationSession:
    id: str
    question: str
    brief: ResearchBrief | None = None
    status: str = "running"
    tree: Tree = field(default_factory=Tree)
    events: list[dict] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    tasks: set[asyncio.Task] = field(default_factory=set)
    active_operations: int = 0
    operation_failed: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))

    async def publish(self, event: dict) -> None:
        async with self.lock:
            self.events.append(event)
            self.last_accessed = datetime.now(UTC)
            subscribers = tuple(self.subscribers)
        for queue in subscribers:
            queue.put_nowait(event)

    def begin_operation(self) -> None:
        if self.active_operations == 0:
            self.operation_failed = False
        self.active_operations += 1
        self.status = "running"

    async def finish_operation(self, failed: bool = False) -> None:
        async with self.lock:
            self.active_operations = max(0, self.active_operations - 1)
            self.operation_failed = self.operation_failed or failed
            if self.active_operations == 0:
                self.status = (
                    "failed" if self.operation_failed else "completed"
                )

    async def subscribe(self) -> tuple[list[dict], asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue()
        async with self.lock:
            self.subscribers.add(queue)
            self.last_accessed = datetime.now(UTC)
            backlog = list(self.events)
        return backlog, queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self.lock:
            self.subscribers.discard(queue)

    def snapshot(self) -> dict:
        brief = self.brief or ResearchBrief.create(self.question)
        return {
            "sessionId": self.id,
            "question": self.question,
            "brief": brief.to_dict(),
            "status": self.status,
            "nodes": [node.to_dict() for node in self.tree.nodes.values()],
        }

    def artifact(self, limit: int = 8) -> dict:
        brief = self.brief or ResearchBrief.create(self.question)
        completed = sorted(
            (
                node
                for node in self.tree.nodes.values()
                if node.parent_id and node.status == "done" and node.insight
            ),
            key=lambda node: (node.depth, node.id),
        )
        findings = []
        for node in completed[:limit]:
            sources = [
                {
                    "title": source.get("title") or source.get("url"),
                    "url": source.get("url"),
                }
                for source in node.sources
                if source.get("url")
            ][:1]
            findings.append(
                {
                    "nodeId": node.id,
                    "title": node.label,
                    "insight": node.insight,
                    "verticals": node.verticals,
                    "sources": sources,
                }
            )
        return {
            "type": "exploretree.research-artifact",
            "sessionId": self.id,
            "status": self.status,
            "brief": brief.to_dict(),
            "coverage": {
                "completedNodes": len(completed),
                "maximumDepth": max(
                    (node.depth for node in completed),
                    default=0,
                ),
                "verticals": sorted(
                    {
                        vertical
                        for node in completed
                        for vertical in node.verticals
                    }
                ),
            },
            "keyFindings": findings,
        }


class SessionManager:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._sessions: dict[str, ExplorationSession] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def get(self, session_id: str) -> ExplorationSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        session.last_accessed = datetime.now(UTC)
        return session

    def start(
        self,
        question: str,
        *,
        brief: ResearchBrief | None = None,
        max_depth: int | None = None,
        breadth: int | None = None,
    ) -> ExplorationSession:
        self._remove_expired()
        brief = brief or ResearchBrief.create(question)
        session = ExplorationSession(
            id=str(uuid4()),
            question=question,
            brief=brief,
        )
        self._sessions[session.id] = session
        self._spawn(
            session,
            explore(
                question,
                session.publish,
                session.tree,
                max_depth=max_depth,
                breadth=breadth,
                research_brief=brief,
            ),
        )
        return session

    def expand(self, session_id: str, node_id: str) -> ExplorationSession:
        session = self.get(session_id)
        if node_id not in session.tree.nodes:
            raise ValueError(f"Unknown node: {node_id}")
        self._spawn(
            session,
            expand_on_demand(
                session.tree,
                node_id,
                session.publish,
                research_brief=session.brief,
            ),
        )
        return session

    def follow_up(
        self, session_id: str, parent_id: str, query: str
    ) -> ExplorationSession:
        session = self.get(session_id)
        if parent_id not in session.tree.nodes:
            raise ValueError(f"Unknown parent node: {parent_id}")
        self._spawn(
            session,
            add_followup(session.tree, parent_id, query, session.publish),
        )
        return session

    def fetch_media(self, session_id: str, node_id: str) -> ExplorationSession:
        session = self.get(session_id)
        if node_id not in session.tree.nodes:
            raise ValueError(f"Unknown node: {node_id}")
        self._spawn(session, get_media(session.tree, node_id, session.publish))
        return session

    def _spawn(self, session: ExplorationSession, operation) -> None:
        session.begin_operation()

        async def run() -> None:
            failed = False
            try:
                await operation
            except asyncio.CancelledError:
                failed = True
                raise
            except Exception:
                failed = True
                logger.exception("Exploration session operation failed")
                await session.publish(
                    {
                        "type": "error",
                        "message": "The exploration operation failed.",
                    }
                )
            finally:
                await session.finish_operation(failed=failed)

        task = asyncio.create_task(run())
        session.tasks.add(task)
        task.add_done_callback(session.tasks.discard)

    def _remove_expired(self) -> None:
        cutoff = datetime.now(UTC) - self._ttl
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.last_accessed < cutoff and not session.tasks
        ]
        for session_id in expired:
            del self._sessions[session_id]


sessions = SessionManager(ttl_seconds=settings.session_ttl_seconds)
