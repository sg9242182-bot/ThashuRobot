import unittest
from unittest.mock import patch

from memory.people import PeopleMemory
from core.decision import get_event_memory_request, get_place_event_query


class UnifiedMemoryTests(unittest.TestCase):
    def setUp(self):
        self.load_patch = patch("memory.people.load_data", return_value={})
        self.save_patch = patch("memory.people.save_data")
        self.load_patch.start()
        self.save_patch.start()
        self.addCleanup(self.load_patch.stop)
        self.addCleanup(self.save_patch.stop)
        self.memory = PeopleMemory()

    def save_event(self, person, text, location):
        return self.memory.remember(
            person, "event", text, confirmed_identity=True, location=location
        )

    def test_event_parser_keeps_only_explicit_user_named_place(self):
        self.assertEqual(
            get_event_memory_request("Remember this event: we met at the library yesterday"),
            ("we met yesterday", "the library"),
        )
        self.assertEqual(
            get_event_memory_request(
                "Remember this event. Yesterday we met at the library."
            ),
            ("Yesterday we met", "the library"),
        )
        self.assertEqual(
            get_event_memory_request("Remember this event: we had a good conversation"),
            ("we had a good conversation", None),
        )

    def test_place_recall_parser_requires_an_explicit_place_label(self):
        self.assertEqual(
            get_place_event_query("What happened at the library?"),
            "the library",
        )
        self.assertIsNone(get_place_event_query("What do you remember about yesterday?"))

    def test_event_links_confirmed_person_place_and_timestamp(self):
        self.assertTrue(self.save_event("Tharun", "Met the team", "Science Hall"))
        recalled = self.memory.recall_at_place(" science   hall ", person="Tharun")
        self.assertEqual(len(recalled), 1)
        event = recalled[0]
        self.assertEqual(event["person"], "Tharun")
        self.assertEqual(event["location"], "Science Hall")
        self.assertEqual(event["text"], "Met the team")
        self.assertRegex(event["saved_at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_place_lookup_is_exact_after_case_and_whitespace_normalization(self):
        self.save_event("Tharun", "Met the team", "Science Hall")
        self.save_event("Uma", "Joined a workshop", "Science  Hall Annex")
        self.assertEqual(len(self.memory.recall_at_place("SCIENCE HALL")), 1)
        self.assertEqual(
            self.memory.recall_at_place("Science Hall Annex")[0]["person"], "Uma"
        )

    def test_place_lookup_can_be_scoped_to_confirmed_person(self):
        self.save_event("Tharun", "Met the team", "Science Hall")
        self.save_event("Uma", "Joined a workshop", "Science Hall")
        result = self.memory.recall_at_place("Science Hall", person="Tharun")
        self.assertEqual([row["person"] for row in result], ["Tharun"])
        self.assertEqual(self.memory.recall_at_place("Science Hall", person="Unknown"), [])

    def test_duplicate_event_ignores_location_case_and_spacing(self):
        self.assertTrue(self.save_event("Tharun", "Met the team", "Science Hall"))
        self.assertFalse(self.save_event("Tharun", "Met the team", " science   hall "))
        self.assertEqual(len(self.memory.recall_at_place("Science Hall")), 1)

    def test_place_recall_is_bounded(self):
        for i in range(8):
            self.save_event("Tharun", f"Event {i}", "Science Hall")
        self.assertEqual(len(self.memory.recall_at_place("Science Hall", limit=20)), 5)


if __name__ == "__main__":
    unittest.main()
