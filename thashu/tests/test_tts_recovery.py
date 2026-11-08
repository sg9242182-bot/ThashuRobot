import io
import subprocess
import unittest
from unittest.mock import patch

from voice import text_to_speech


class FakeProcess:
    def __init__(self, timeout_on_wait=False):
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO()
        self.stderr = None
        self.returncode = None
        self.timeout_on_wait = timeout_on_wait
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.timeout_on_wait and not self.terminated and not self.killed:
            raise subprocess.TimeoutExpired("fake", timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9


class PiperRecoveryTests(unittest.TestCase):
    def test_live_piper_timeout_terminates_children_and_returns(self):
        piper = FakeProcess(timeout_on_wait=True)
        aplay = FakeProcess()
        with (
            patch.object(text_to_speech.subprocess, "Popen", side_effect=[piper, aplay]),
            patch.object(text_to_speech, "TTS_PROCESS_TIMEOUT_SECONDS", 0.01),
        ):
            text_to_speech.speak("A dynamic reply that is not cached.")

        self.assertTrue(aplay.terminated)
        self.assertTrue(piper.terminated)

    def test_successful_live_piper_playback_reaps_both_children(self):
        piper = FakeProcess()
        aplay = FakeProcess()
        with patch.object(
            text_to_speech.subprocess, "Popen", side_effect=[piper, aplay]
        ):
            text_to_speech.speak("A different uncached reply.")

        self.assertEqual(piper.returncode, 0)
        self.assertEqual(aplay.returncode, 0)
        self.assertFalse(piper.terminated)
        self.assertFalse(aplay.terminated)


if __name__ == "__main__":
    unittest.main()
