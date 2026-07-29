import unittest
from unittest.mock import patch

from app.mcp_server import _artifact_text, explore_tree, mcp
from app.sessions import ExplorationSession, sessions


def _fake_start(question, *, brief=None, max_depth=None, breadth=None):
    """Record the brief without spawning real research."""
    return ExplorationSession(id="test-session", question=question, brief=brief)


class ExploreTreeToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_oversized_research_brief_arrays(self) -> None:
        result = await explore_tree(
            "Question",
            scope=[f"item-{index}" for index in range(9)],
        )

        self.assertTrue(result.isError)

    async def test_runtime_schema_limits_research_brief_arrays(self) -> None:
        tools = await mcp.list_tools()
        tool = next(item for item in tools if item.name == "explore_tree")
        properties = tool.inputSchema["properties"]

        self.assertEqual(properties["scope"]["anyOf"][0]["maxItems"], 8)
        self.assertEqual(properties["constraints"]["anyOf"][0]["maxItems"], 8)
        self.assertEqual(properties["options"]["anyOf"][0]["maxItems"], 4)
        self.assertEqual(properties["mode"]["default"], "explore")

    async def test_rejects_an_unsupported_research_mode(self) -> None:
        result = await explore_tree("Question", mode="recommend")

        self.assertTrue(result.isError)

    async def test_accepts_compare_mode_with_options(self) -> None:
        with patch.object(sessions, "start", wraps=_fake_start) as start:
            result = await explore_tree(
                "Which warehouse should we adopt?",
                mode="compare",
                options=["Snowflake", "Databricks"],
            )

        self.assertFalse(result.isError)
        brief = start.call_args.kwargs["brief"]
        self.assertEqual(brief.mode, "compare")
        self.assertEqual(brief.options, ["Snowflake", "Databricks"])

    async def test_results_tool_is_model_visible_without_widget_metadata(self) -> None:
        tools = await mcp.list_tools()
        tool = next(
            item for item in tools if item.name == "get_research_results"
        )

        self.assertEqual(tool.inputSchema["required"], ["session_id"])
        self.assertFalse(tool.meta)
        self.assertIn("Never call in the same conversation turn", tool.description)

    async def test_branch_read_tools_are_model_visible(self) -> None:
        tools = {tool.name: tool for tool in await mcp.list_tools()}

        self.assertFalse(tools["get_tree_outline"].meta)
        self.assertFalse(tools["get_branch_context"].meta)
        self.assertIn(
            "Never call in the same conversation turn as explore_tree",
            tools["get_tree_outline"].description,
        )
        self.assertIn(
            "Never call in the same conversation turn as explore_tree",
            tools["get_branch_context"].description,
        )
        node_ids = tools["get_branch_context"].inputSchema["properties"]["node_ids"]
        self.assertEqual(node_ids["maxItems"], 2)

    async def test_explore_tool_declares_async_same_turn_boundary(self) -> None:
        tools = {tool.name: tool for tool in await mcp.list_tools()}

        self.assertIn(
            "Use this tool whenever the user asks to research",
            tools["explore_tree"].description,
        )
        self.assertIn(
            "instead of answering from general knowledge",
            tools["explore_tree"].description,
        )
        self.assertIn(
            "returns before any findings are available",
            tools["explore_tree"].description,
        )
        self.assertIn(
            "do not call any other tool in the same conversation turn",
            tools["explore_tree"].description,
        )

    async def test_explore_tool_explains_when_to_choose_compare_mode(self) -> None:
        tools = {tool.name: tool for tool in await mcp.list_tools()}

        self.assertIn(
            "Set mode to 'compare' when the user is weighing specific "
            "alternatives against each other",
            tools["explore_tree"].description,
        )


class ComparisonArtifactTextTests(unittest.TestCase):
    def _artifact(self, unfilled):
        return {
            "status": "completed",
            "keyFindings": [],
            "comparison": {
                "options": ["Snowflake", "Databricks"],
                "criteria": ["Cost"],
                "cells": [
                    {
                        "option": "Snowflake",
                        "criterion": "Cost",
                        "nodeId": "n7",
                        "insight": "Consumption pricing dominates.",
                        "evidenceCoverage": {"sourceCount": 3, "domainCount": 2},
                    }
                ],
                "unfilledCells": unfilled,
                "complete": not unfilled,
            },
        }

    def test_renders_the_aligned_grid_for_copilot(self) -> None:
        text = _artifact_text(self._artifact([]))

        self.assertIn("aligned comparison of Snowflake, Databricks", text)
        self.assertIn("[n7] Snowflake — Cost: Consumption pricing dominates.", text)
        self.assertIn("3 unique sources across 2 domains", text)

    def test_names_unfilled_cells_so_gaps_are_not_inferred(self) -> None:
        text = _artifact_text(
            self._artifact([{"option": "Databricks", "criterion": "Cost"}])
        )

        self.assertIn("Databricks — Cost", text)
        self.assertIn("comparison is incomplete", text)

    def test_states_gaps_without_instructing_the_model(self) -> None:
        # Copilot's prompt-injection classifier blocks the turn when tool output
        # reads as instructions aimed at the model, so the artifact reports facts
        # only. The behavioural guidance lives in the agent instructions instead.
        text = _artifact_text(
            self._artifact([{"option": "Databricks", "criterion": "Cost"}])
        )

        for directive in ("Say so rather", "Do not declare", "Compare only on"):
            self.assertNotIn(directive, text)

    def test_running_comparison_withholds_conclusions(self) -> None:
        artifact = self._artifact([])
        artifact["status"] = "running"

        self.assertIn("still researching", _artifact_text(artifact))
