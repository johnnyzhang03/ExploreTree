"""Exploration sessions shared by MCP tools and WebSocket clients."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .agent import add_followup, expand_on_demand, explore, get_media
from .config import settings
from .research_brief import ResearchBrief
from .tree import Tree, evidence_coverage

logger = logging.getLogger(__name__)


class SessionNotFoundError(KeyError):
    pass


def _compact_text(value: str, limit: int = 320) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


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
    completion_handoff_claimed: bool = False
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

    async def claim_completion_handoff(self) -> bool:
        async with self.lock:
            if self.completion_handoff_claimed:
                return False
            self.completion_handoff_claimed = True
            return True

    async def release_completion_handoff(self) -> None:
        async with self.lock:
            self.completion_handoff_claimed = False

    def snapshot(self) -> dict:
        brief = self.brief or ResearchBrief.create(self.question)
        return {
            "sessionId": self.id,
            "question": self.question,
            "brief": brief.to_dict(),
            "status": self.status,
            "mode": self.tree.mode,
            "comparison": self.tree.comparison,
            "nodes": [node.to_dict() for node in self.tree.nodes.values()],
        }

    def _path_to(self, node_id: str) -> list[dict]:
        path = []
        seen = set()
        current = self.tree.nodes[node_id]
        while current and current.id not in seen:
            seen.add(current.id)
            path.append({"nodeId": current.id, "title": current.label})
            current = (
                self.tree.nodes.get(current.parent_id)
                if current.parent_id
                else None
            )
        return list(reversed(path))

    def tree_outline(self, limit: int = 80) -> dict:
        children: dict[str, list[str]] = {}
        for node in self.tree.nodes.values():
            if node.parent_id:
                children.setdefault(node.parent_id, []).append(node.id)

        ordered = sorted(
            self.tree.nodes.values(),
            key=lambda node: (node.depth, node.id),
        )
        nodes = []
        for node in ordered[:limit]:
            coverage = evidence_coverage(node.sources)
            nodes.append({
                "nodeId": node.id,
                "parentId": node.parent_id,
                "title": node.label,
                "path": [item["title"] for item in self._path_to(node.id)],
                "status": node.status,
                "childCount": len(children.get(node.id, [])),
                "evidenceCount": coverage["sourceCount"],
                "evidenceCoverage": coverage,
                "insight": _compact_text(node.insight, 180),
                **(
                    {"option": node.option, "criterion": node.criterion}
                    if node.option or node.criterion
                    else {}
                ),
            })
        return {
            "type": "exploretree.tree-outline",
            "sessionId": self.id,
            "status": self.status,
            "mode": self.tree.mode,
            "comparison": self.tree.comparison,
            "nodes": nodes,
            "truncated": len(ordered) > limit,
        }

    def branch_context(self, node_ids: list[str], limit: int = 12) -> dict:
        unknown = [node_id for node_id in node_ids if node_id not in self.tree.nodes]
        if unknown:
            raise ValueError(f"Unknown node: {unknown[0]}")

        children: dict[str, list[str]] = {}
        for node in self.tree.nodes.values():
            if node.parent_id:
                children.setdefault(node.parent_id, []).append(node.id)

        branches = []
        for node_id in dict.fromkeys(node_ids):
            root = self.tree.nodes[node_id]
            pending = [node_id]
            subtree_ids = []
            while pending:
                current_id = pending.pop(0)
                subtree_ids.append(current_id)
                pending.extend(children.get(current_id, []))

            subtree = sorted(
                (self.tree.nodes[item_id] for item_id in subtree_ids),
                key=lambda node: (node.depth, node.id),
            )
            findings = []
            for node in subtree[:limit]:
                coverage = evidence_coverage(node.sources)
                findings.append(
                    {
                        "nodeId": node.id,
                        "parentId": node.parent_id,
                        "title": node.label,
                        "status": node.status,
                        "insight": _compact_text(node.insight),
                        "evidenceCount": coverage["sourceCount"],
                        "evidenceCoverage": coverage,
                        **(
                            {"option": node.option, "criterion": node.criterion}
                            if node.option or node.criterion
                            else {}
                        ),
                        "sources": [
                            {
                                "title": source.get("title") or source.get("url"),
                                "url": source.get("url"),
                                "domain": source.get("domain"),
                                "publishedAt": source.get("publishedAt"),
                            }
                            for source in node.sources
                            if source.get("url")
                        ][:2],
                    }
                )
            branches.append(
                {
                    "nodeId": root.id,
                    "title": root.label,
                    "path": self._path_to(root.id),
                    "findings": findings,
                    "truncated": len(subtree) > limit,
                }
            )

        return {
            "type": "exploretree.branch-context",
            "sessionId": self.id,
            "status": self.status,
            "mode": self.tree.mode,
            "branches": branches,
        }

    def comparison_matrix(self) -> dict | None:
        """The aligned options x criteria grid, with unfilled cells named explicitly.

        Only the primary criteria grid is reported; deeper sub-criteria stay in the
        tree outline so the matrix remains compact and genuinely comparable.
        """
        frame = self.tree.comparison
        if not frame:
            return None

        options = frame.get("options", [])
        criteria = frame.get("criteria", [])
        by_cell = {}
        for node in self.tree.nodes.values():
            # The primary grid is exactly depth 2: options sit at depth 1 and
            # deeper sub-criteria must not displace a real cell.
            if node.depth != 2 or not node.option or not node.criterion:
                continue
            key = (node.option, node.criterion)
            if key in by_cell or node.criterion not in criteria:
                continue
            by_cell[key] = node

        cells = []
        missing = []
        for option in options:
            for criterion in criteria:
                node = by_cell.get((option, criterion))
                if node is None or node.status != "done" or not node.insight:
                    missing.append({"option": option, "criterion": criterion})
                    continue
                cells.append(
                    {
                        "option": option,
                        "criterion": criterion,
                        "nodeId": node.id,
                        "insight": _compact_text(node.insight),
                        "evidenceCoverage": evidence_coverage(node.sources),
                    }
                )
        return {
            "options": options,
            "criteria": criteria,
            "cells": cells,
            "unfilledCells": missing,
            "complete": not missing,
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
            node_coverage = evidence_coverage(node.sources)
            sources = [
                {
                    "title": source.get("title") or source.get("url"),
                    "url": source.get("url"),
                    "domain": source.get("domain"),
                    "publishedAt": source.get("publishedAt"),
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
                    "evidenceCoverage": node_coverage,
                    "sources": sources,
                }
            )
        all_sources = [
            source
            for node in completed
            for source in node.sources
        ]
        aggregate_coverage = evidence_coverage(all_sources)
        matrix = self.comparison_matrix()
        return {
            "type": "exploretree.research-artifact",
            "sessionId": self.id,
            "status": self.status,
            "mode": self.tree.mode,
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
                "evidence": aggregate_coverage,
                "evidenceGapNodes": sum(
                    evidence_coverage(node.sources)["gaps"]["noEvidence"]
                    for node in completed
                ),
            },
            "keyFindings": findings,
            "comparison": matrix,
            "treeOutline": self.tree_outline()["nodes"],
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
