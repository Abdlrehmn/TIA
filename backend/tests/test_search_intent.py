"""Deterministic tests for current-information search intent."""

import unittest

from app.services.search_intent import needs_web_search


class SearchIntentTests(unittest.TestCase):
    def test_current_information_prompts_trigger_search(self):
        messages = (
            "Tell me the latest GTA 6 news.",
            "What happened in AI today?",
            "What is the latest Python version?",
            "Who won yesterday's match?",
            "What are the recent updates about OpenAI?",
            "What's the current weather in Lahore?",
            "How much does this product cost right now?",
            "What are the current government policies?",
            "Aaj ki AI khabrein kya hain?",
            "Kal ke match mein kis ne jeeta?",
            "Is waqt Lahore ka mausam kaisa hai?",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertTrue(needs_web_search(message))

    def test_general_knowledge_and_coding_prompts_do_not_trigger_search(self):
        messages = (
            "What is Python?",
            "Explain OOP.",
            "What is machine learning?",
            "Explain neural networks.",
            "Write a Python function to reverse a string.",
            "How does an API work?",
            "Explain version control.",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertFalse(needs_web_search(message))


if __name__ == "__main__":
    unittest.main()
