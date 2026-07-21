import unittest

from app import llm
from app.agent import _fallback_decompose
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


class ProviderDiagnosticsTests(unittest.TestCase):
    def test_error_diagnostics_exclude_message_content(self) -> None:
        error = RuntimeError("secret provider response")
        error.status_code = 403

        llm.record_error("plan", error)

        diagnostics = llm.provider_diagnostics()
        self.assertEqual(
            diagnostics["lastError"],
            {"operation": "plan", "type": "RuntimeError", "status": 403},
        )
        self.assertNotIn("secret provider response", repr(diagnostics))
