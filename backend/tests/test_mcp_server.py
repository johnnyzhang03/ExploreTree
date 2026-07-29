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
            "returns before any findings are available",
            tools["explore_tree"].description,
        )
        self.assertIn(
            "do not call any other tool in the same conversation turn",
            tools["explore_tree"].description,
        )
