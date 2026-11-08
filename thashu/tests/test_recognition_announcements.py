import unittest

from core.decision import should_announce_recognized_person


class RecognitionAnnouncementTests(unittest.TestCase):
    def test_first_recognized_person_is_announced(self):
        self.assertTrue(should_announce_recognized_person("Tharun", None))

    def test_same_person_is_silent_after_conversation(self):
        self.assertFalse(should_announce_recognized_person("Tharun", "Tharun"))

    def test_identity_comparison_ignores_name_case_and_outer_spaces(self):
        self.assertFalse(should_announce_recognized_person(" tharun ", "Tharun"))

    def test_different_person_is_announced(self):
        self.assertTrue(should_announce_recognized_person("Durai", "Tharun"))

    def test_unknown_or_empty_identity_is_never_announced(self):
        self.assertFalse(should_announce_recognized_person("Unknown", "Tharun"))
        self.assertFalse(should_announce_recognized_person("", None))
        self.assertFalse(should_announce_recognized_person(None, None))


if __name__ == "__main__":
    unittest.main()
