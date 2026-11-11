import unittest

from hardware.shutdown_button import ButtonGesture


class ButtonGestureTests(unittest.TestCase):
    def test_short_click_opens_ble_on_release(self):
        button = ButtonGesture()
        self.assertIsNone(button.update(True, 10.0))
        self.assertIsNone(button.update(True, 10.1))
        self.assertEqual(button.update(False, 10.12), "ble")

    def test_three_second_hold_shuts_down_once(self):
        button = ButtonGesture()
        self.assertIsNone(button.update(True, 2.0))
        self.assertIsNone(button.update(True, 4.99))
        self.assertEqual(button.update(True, 5.0), "shutdown")
        self.assertIsNone(button.update(True, 5.2))
        self.assertIsNone(button.update(False, 5.3))

    def test_hold_is_detected_if_release_is_first_poll_after_threshold(self):
        button = ButtonGesture()
        self.assertIsNone(button.update(True, 1.0))
        self.assertEqual(button.update(False, 4.1), "shutdown")

    def test_contact_bounce_shorter_than_debounce_is_ignored(self):
        button = ButtonGesture()
        self.assertIsNone(button.update(True, 0.0))
        self.assertIsNone(button.update(False, 0.03))

    def test_idle_button_does_nothing(self):
        self.assertIsNone(ButtonGesture().update(False, 1.0))


if __name__ == "__main__":
    unittest.main()
