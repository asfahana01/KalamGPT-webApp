import unittest

from backend.kalam_ai.orchestrator import route_question, verify_response


class OrchestratorTests(unittest.TestCase):
    def test_simple_question_uses_personality(self):
        decision = route_question("Hello, who are you?")
        self.assertEqual(decision.active_layers, ["personality"])
        self.assertEqual(decision.task_type, "conversation")

    def test_reasoning_question_uses_reasoning(self):
        decision = route_question("Why are students not becoming innovative?")
        self.assertIn("personality", decision.active_layers)
        self.assertIn("reasoning", decision.active_layers)
        self.assertTrue(decision.needs_reasoning_plan)

    def test_idea_question_uses_innovation(self):
        decision = route_question("Create an idea for improving rural education.")
        self.assertIn("innovation", decision.active_layers)
        self.assertTrue(decision.needs_innovation)

    def test_mixed_question_uses_both(self):
        decision = route_question("How can youth create an innovative energy solution for India?")
        self.assertIn("reasoning", decision.active_layers)
        self.assertIn("innovation", decision.active_layers)

    def test_identity_claim_is_flagged(self):
        result = verify_response("Who are you?", "I am Dr. A. P. J. Abdul Kalam.", [])
        self.assertFalse(result["identity_safe"])
        self.assertTrue(result["needs_review"])

    def test_quote_without_sources_is_flagged(self):
        result = verify_response("What did Kalam say?", "Kalam said, 'Never give up.'", [])
        self.assertTrue(result["quote_review_needed"])


if __name__ == "__main__":
    unittest.main()
