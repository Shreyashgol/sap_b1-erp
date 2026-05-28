import unittest

from app.operations.conversation_memory import build_contextual_prompt, normalize_conversation_history


class ConversationMemoryTest(unittest.TestCase):
    def test_normalizes_recent_user_and_assistant_messages(self):
        history = [
            {"role": "system", "content": "ignore"},
            {"role": "user", "content": "Show latest purchase orders"},
            {"role": "assistant", "content": "Here are the latest purchase orders"},
        ]

        normalized = normalize_conversation_history(history)

        self.assertEqual(
            normalized,
            [
                {"role": "user", "content": "Show latest purchase orders"},
                {"role": "assistant", "content": "Here are the latest purchase orders"},
            ],
        )

    def test_contextual_prompt_keeps_current_request_visible(self):
        prompt = build_contextual_prompt(
            "Now show the invoices for the same vendor",
            [{"role": "user", "content": "Show purchase orders for vendor V100"}],
        )

        self.assertIn("Previous conversation context", prompt)
        self.assertIn("Show purchase orders for vendor V100", prompt)
        self.assertIn("Current user request", prompt)
        self.assertIn("Now show the invoices for the same vendor", prompt)


if __name__ == "__main__":
    unittest.main()
