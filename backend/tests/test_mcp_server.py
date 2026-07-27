import unittest

from app.mcp_server import explore_tree, mcp


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

    async def test_results_tool_is_model_visible_without_widget_metadata(self) -> None:
        tools = await mcp.list_tools()
        tool = next(
            item for item in tools if item.name == "get_research_results"
        )

        self.assertEqual(tool.inputSchema["required"], ["session_id"])
        self.assertFalse(tool.meta)
        self.assertIn("Never call in the same conversation turn", tool.description)
