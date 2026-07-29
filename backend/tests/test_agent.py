import unittest
from unittest.mock import patch

from app import llm
from app.agent import _apply_option, _fallback_decompose, _infer_options, explore
from app.research_brief import ResearchBrief
from app.search import SearchResult, deduplicate_results
from app.tree import Tree


class FallbackPlannerTests(unittest.TestCase):
    def test_topics_have_distinct_titles_and_queries(self) -> None:
        topics = _fallback_decompose("Why is demand increasing?")

        self.assertEqual(len({topic.title for topic in topics}), 3)
        self.assertEqual(len({topic.query for topic in topics}), 3)
        self.assertTrue(
            all("Why is demand increasing" in topic.query for topic in topics)
        )


class CardImageTests(unittest.IsolatedAsyncioTestCase):
    async def test_tree_claims_each_card_image_once(self) -> None:
        tree = Tree()
        images = [
            {"thumbnail": "https://example.com/one.jpg"},
            {"thumbnail": "https://example.com/two.jpg"},
        ]

        self.assertEqual(await tree.claim_card_image(images), images[0])
        self.assertEqual(await tree.claim_card_image(images), images[1])
        self.assertEqual(await tree.claim_card_image(images), {})


class SearchResultTests(unittest.TestCase):
    def test_source_metadata_and_tracking_url_deduplication(self) -> None:
        results = [
            SearchResult(
                title="First",
                url="https://www.example.com/report?utm_source=newsletter",
                snippet="One",
                published_at="2026-07-28",
            ),
            SearchResult(
                title="Duplicate",
                url="https://example.com/report",
                snippet="Two",
            ),
        ]

        unique = deduplicate_results(results)

        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].to_dict()["domain"], "example.com")
        self.assertEqual(
            unique[0].to_dict()["canonicalUrl"],
            "https://example.com/report",
        )
        self.assertEqual(unique[0].to_dict()["publishedAt"], "2026-07-28")


class ProviderDiagnosticsTests(unittest.TestCase):
    def test_error_diagnostics_exclude_message_content(self) -> None:
        error = RuntimeError("secret provider response")
        error.status_code = 403

        llm.record_error("plan", error)

        diagnostics = llm.provider_diagnostics()
        self.assertEqual(
            diagnostics["lastError"],
            {
                "operation": "plan",
                "type": "RuntimeError",
                "status": 403,
                "causes": [],
            },
        )
        self.assertNotIn("secret provider response", repr(diagnostics))


async def _stub_expand(tree, node_id, emit):
    """Stand in for search + synthesis so growth structure can be tested offline."""
    node = tree.nodes[node_id]
    node.status = "done"
    node.insight = f"insight for {node.query}"
    await emit({"type": "node_updated", "node": node.to_dict()})


async def _no_plan(*args, **kwargs):
    return None


async def _no_topics(*args, **kwargs):
    return []


class CriterionQueryTests(unittest.TestCase):
    def test_option_placeholder_is_substituted(self) -> None:
        self.assertEqual(
            _apply_option("{option} pricing and total cost", "Snowflake"),
            "Snowflake pricing and total cost",
        )

    def test_template_without_placeholder_is_prefixed_with_the_option(self) -> None:
        self.assertEqual(
            _apply_option("pricing and total cost", "Snowflake"),
            "Snowflake pricing and total cost",
        )


class InferOptionsTests(unittest.TestCase):
    def test_splits_named_alternatives(self) -> None:
        self.assertEqual(
            _infer_options("Compare Snowflake vs Databricks?"),
            ["Snowflake", "Databricks"],
        )

    def test_returns_nothing_for_an_open_ended_question(self) -> None:
        self.assertEqual(
            _infer_options("What's driving the surge in AI chip demand?"), []
        )


class ComparisonPlanValidationTests(unittest.TestCase):
    def test_fewer_than_two_distinct_options_is_not_a_comparison(self) -> None:
        criteria = [llm.ComparisonCriterion(name="Cost", query_template="{option} cost")]

        for options in (
            [],
            [llm.ComparisonOption(name="Snowflake")],
            [
                llm.ComparisonOption(name="Snowflake"),
                llm.ComparisonOption(name=" snowflake "),
            ],
            [llm.ComparisonOption(name="  "), llm.ComparisonOption(name="")],
        ):
            with self.subTest(options=[option.name for option in options]):
                self.assertIsNone(llm._clean_comparison(options, criteria))

    def test_missing_criteria_do_not_invalidate_real_options(self) -> None:
        plan = llm._clean_comparison(
            [
                llm.ComparisonOption(name="Snowflake"),
                llm.ComparisonOption(name="Databricks"),
            ],
            [],
        )

        self.assertIsNotNone(plan)
        self.assertEqual([option.name for option in plan.options], ["Snowflake", "Databricks"])
        self.assertEqual(plan.criteria, [])

    def test_criteria_are_deduplicated_and_grounded_in_web(self) -> None:
        criteria = llm._clean_criteria(
            [
                llm.ComparisonCriterion(
                    name="Cost", query_template="{option} cost", verticals=["finance"]
                ),
                llm.ComparisonCriterion(name=" cost ", query_template="dupe"),
            ]
        )

        self.assertEqual(len(criteria), 1)
        self.assertEqual(criteria[0].verticals, ["web", "finance"])


class CompareModeGrowthTests(unittest.IsolatedAsyncioTestCase):
    """Growth-structure tests. Every LLM step is stubbed out so these exercise the
    deterministic fallback tier offline; the structural invariants they assert are
    enforced by the growth loop, not by the model."""

    async def _grow(self, brief, max_depth=2, breadth=1):
        tree = Tree()
        events = []

        async def emit(event):
            events.append(event)

        with (
            patch("app.agent._expand_node", _stub_expand),
            patch("app.agent.llm.plan_comparison", _no_plan),
            patch("app.agent.llm.plan_criteria", _no_topics),
            patch("app.agent.llm.reflect_criteria", _no_topics),
            patch("app.agent.llm.plan", _no_topics),
            patch("app.agent.llm.reflect", _no_topics),
        ):
            await explore(
                brief.question,
                emit,
                tree,
                max_depth=max_depth,
                breadth=breadth,
                research_brief=brief,
            )
        return tree, events

    async def test_criteria_are_applied_identically_to_every_option(self) -> None:
        brief = ResearchBrief.create(
            "Which warehouse should we adopt?",
            mode="compare",
            options=["Snowflake", "Databricks", "BigQuery"],
        )

        tree, events = await self._grow(brief)

        self.assertEqual(tree.mode, "compare")
        options = [n for n in tree.nodes.values() if n.depth == 1]
        self.assertEqual(
            [node.label for node in options],
            ["Snowflake", "Databricks", "BigQuery"],
        )

        # Every option must carry the same criteria, in the same order — that
        # ordering is what makes the comparison read as aligned rows.
        criteria_by_option = {}
        for node in tree.nodes.values():
            if node.depth == 2:
                criteria_by_option.setdefault(node.option, []).append(node.criterion)
        self.assertEqual(
            set(criteria_by_option), {"Snowflake", "Databricks", "BigQuery"}
        )
        orders = list(criteria_by_option.values())
        self.assertTrue(all(order == orders[0] for order in orders))
        self.assertEqual(len(orders[0]), 3)

    async def test_each_comparison_cell_queries_its_own_option(self) -> None:
        brief = ResearchBrief.create(
            "Which warehouse should we adopt?",
            mode="compare",
            options=["Snowflake", "Databricks"],
        )

        tree, _ = await self._grow(brief)

        for node in tree.nodes.values():
            if node.depth == 2:
                self.assertIn(node.option, node.query)

    async def test_deeper_rounds_stay_symmetric_across_options(self) -> None:
        brief = ResearchBrief.create(
            "Which warehouse should we adopt?",
            mode="compare",
            options=["Snowflake", "Databricks"],
        )

        tree, _ = await self._grow(brief, max_depth=3, breadth=1)

        deep = [node for node in tree.nodes.values() if node.depth == 3]
        self.assertTrue(deep)
        per_option = {}
        for node in deep:
            per_option.setdefault(node.option, []).append(node.criterion)
        self.assertEqual(set(per_option), {"Snowflake", "Databricks"})
        self.assertEqual(
            sorted(per_option["Snowflake"]), sorted(per_option["Databricks"])
        )

    async def test_comparison_frame_is_announced_to_the_widget(self) -> None:
        brief = ResearchBrief.create(
            "Which warehouse should we adopt?",
            mode="compare",
            options=["Snowflake", "Databricks"],
        )

        _, events = await self._grow(brief)

        mode_event = next(event for event in events if event["type"] == "mode")
        self.assertEqual(mode_event["mode"], "compare")
        self.assertEqual(mode_event["options"], ["Snowflake", "Databricks"])
        self.assertEqual(len(mode_event["criteria"]), 3)

    async def test_compare_without_resolvable_options_degrades_to_explore(self) -> None:
        brief = ResearchBrief.create(
            "What's driving the surge in AI chip demand?",
            mode="compare",
        )

        tree, events = await self._grow(brief)

        self.assertEqual(tree.mode, "explore")
        mode_event = next(event for event in events if event["type"] == "mode")
        self.assertEqual(mode_event["mode"], "explore")
        self.assertEqual(mode_event["requestedMode"], "compare")
        self.assertTrue(
            all(not node.criterion for node in tree.nodes.values())
        )

    async def test_explore_mode_is_unaffected(self) -> None:
        brief = ResearchBrief.create("What's driving AI chip demand?")

        tree, events = await self._grow(brief)

        self.assertEqual(tree.mode, "explore")
        self.assertIsNone(tree.comparison)
        self.assertFalse([event for event in events if event["type"] == "mode"])
        self.assertTrue(
            all(
                not node.option and not node.criterion
                for node in tree.nodes.values()
            )
        )
