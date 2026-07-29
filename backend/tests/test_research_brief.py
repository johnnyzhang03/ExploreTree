import unittest

from app.research_brief import ResearchBrief, normalize_mode


class ResearchBriefTests(unittest.TestCase):
    def test_create_normalizes_optional_context(self) -> None:
        brief = ResearchBrief.create(
            "  Should we enter this market?  ",
            objective="  Support an investment decision ",
            audience=" Executive team ",
            scope=[" competitors ", "", "market size"],
            constraints=["Exclude private companies", " "],
            freshness=" last 12 months ",
            desired_output=" recommendation ",
        )

        self.assertEqual(brief.question, "Should we enter this market?")
        self.assertEqual(brief.scope, ["competitors", "market size"])
        self.assertEqual(brief.constraints, ["Exclude private companies"])
        self.assertIn(
            "Decision or objective: Support an investment decision",
            brief.planning_prompt(),
        )

    def test_planning_prompt_identifies_current_branch(self) -> None:
        brief = ResearchBrief.create(
            "Should we enter this market?",
            scope=["market size", "risks"],
        )

        prompt = brief.planning_prompt("Regulatory barriers")

        self.assertIn("Required scope: market size; risks", prompt)
        self.assertIn(
            "Current branch to investigate: Regulatory barriers",
            prompt,
        )


class ResearchModeTests(unittest.TestCase):
    def test_defaults_to_explore_mode_without_options(self) -> None:
        brief = ResearchBrief.create("Why is demand rising?")

        self.assertEqual(brief.mode, "explore")
        self.assertEqual(brief.options, [])
        self.assertFalse(brief.is_comparison)
        self.assertNotIn("Research mode", brief.planning_prompt())

    def test_unrecognized_mode_degrades_to_explore(self) -> None:
        for candidate in ("recommend", "", "  ", "nonsense", None):
            with self.subTest(mode=candidate):
                self.assertEqual(normalize_mode(candidate), "explore")

    def test_compare_mode_normalizes_and_deduplicates_options(self) -> None:
        brief = ResearchBrief.create(
            "Which warehouse should we adopt?",
            mode=" COMPARE ",
            options=[" Snowflake ", "Databricks", "snowflake ", "", "Snowflake"],
        )

        self.assertEqual(brief.mode, "compare")
        self.assertTrue(brief.is_comparison)
        self.assertEqual(
            brief.options, ["Snowflake", "Databricks", "snowflake"]
        )

    def test_compare_mode_states_the_frame_in_the_planning_prompt(self) -> None:
        brief = ResearchBrief.create(
            "Which warehouse should we adopt?",
            mode="compare",
            options=["Snowflake", "Databricks"],
        )

        prompt = brief.planning_prompt()

        self.assertIn("Research mode: compare", prompt)
        self.assertIn("Options to compare: Snowflake; Databricks", prompt)

    def test_mode_and_options_are_serialized(self) -> None:
        brief = ResearchBrief.create(
            "Which warehouse?", mode="compare", options=["A", "B"]
        )

        payload = brief.to_dict()

        self.assertEqual(payload["mode"], "compare")
        self.assertEqual(payload["options"], ["A", "B"])
