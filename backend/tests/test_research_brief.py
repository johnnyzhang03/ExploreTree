import unittest

from app.research_brief import ResearchBrief


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
