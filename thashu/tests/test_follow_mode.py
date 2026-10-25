import unittest

from core.decision import get_follow_command
from vision.follow_logic import FollowLogic


def face(track_id, x, ambiguous=False):
    return {
        "track_id": track_id,
        "center": (x, 200),
        "bbox": (x - 20, 180, x + 20, 220),
        "ambiguous": ambiguous,
    }


def snapshot(faces, observed_at=10.0):
    return {"faces": faces, "observed_at": observed_at, "frame_size": (640, 480)}


class FollowCommandTests(unittest.TestCase):
    def test_only_exact_follow_phrases_dispatch(self):
        self.assertEqual(get_follow_command("Follow me"), "START")
        self.assertEqual(get_follow_command("stop following"), "STOP")
        self.assertEqual(get_follow_command("follow the person on the left"), "LEFT")
        self.assertEqual(get_follow_command("follow the person in the center"), "CENTER")
        self.assertEqual(get_follow_command("follow the person on the right"), "RIGHT")
        self.assertIsNone(get_follow_command("I want you to follow me later"))
        self.assertIsNone(get_follow_command("move forward"))


class FollowLogicTests(unittest.TestCase):
    def setUp(self):
        self.logic = FollowLogic()
        self.logic.start()

    def test_selects_only_single_fresh_unambiguous_face(self):
        result = self.logic.update(snapshot([face(4, 320)]), now=10.1)
        self.assertEqual(result["state"], FollowLogic.TRACKING)
        self.assertEqual(result["target"]["track_id"], 4)
        self.assertFalse(result["stop_motion"])

    def test_multiple_faces_require_unique_region_selection(self):
        faces = [face(1, 100), face(2, 400)]
        result = self.logic.update(snapshot(faces), now=10.1)
        self.assertEqual(result["state"], FollowLogic.SELECTING_TARGET)
        self.assertIsNone(result["target"])

        self.assertTrue(self.logic.request_region("RIGHT"))
        result = self.logic.update(snapshot(faces), now=10.2)
        self.assertEqual(result["target"]["track_id"], 2)

    def test_duplicate_faces_in_requested_region_are_rejected(self):
        faces = [face(1, 410), face(2, 500)]
        self.logic.update(snapshot(faces), now=10.1)
        self.logic.request_region("RIGHT")
        result = self.logic.update(snapshot(faces), now=10.2)
        self.assertIsNone(result["target"])
        self.assertEqual(result["state"], FollowLogic.SELECTING_TARGET)

    def test_ambiguous_target_stops_and_requires_reselection(self):
        self.logic.update(snapshot([face(1, 320)]), now=10.1)
        result = self.logic.update(snapshot([face(1, 322, ambiguous=True)]), now=10.2)
        self.assertTrue(result["stop_motion"])
        self.assertEqual(result["state"], FollowLogic.NEEDS_RESELECTION)
        self.assertIsNone(result["target"])

    def test_target_loss_never_transfers_to_another_face(self):
        self.logic.update(snapshot([face(1, 320)]), now=10.1)
        result = self.logic.update(snapshot([face(2, 320)]), now=10.2)
        self.assertTrue(result["stop_motion"])
        self.assertIsNone(result["target"])
        self.assertEqual(self.logic.target_id, 1)

    def test_stale_frames_stop_existing_tracking(self):
        self.logic.update(snapshot([face(1, 320)]), now=10.1)
        result = self.logic.update(snapshot([face(1, 320)], observed_at=9.0), now=10.2)
        self.assertTrue(result["stop_motion"])
        self.assertIsNone(result["target"])

    def test_runtime_interaction_cancels_follow(self):
        self.logic.update(snapshot([face(1, 320)]), now=10.1)
        result = self.logic.update(snapshot([]), runtime_idle=False, now=10.2)
        self.assertTrue(result["stop_motion"])
        self.assertFalse(self.logic.enabled)
        self.assertEqual(result["state"], FollowLogic.OFF)


if __name__ == "__main__":
    unittest.main()
