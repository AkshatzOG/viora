import unittest
from agent.brain import MusicBrain


class BrainTests(unittest.TestCase):
    def setUp(self):
        self.brain = MusicBrain()

    def test_exact_play(self):
        x = self.brain.understand("play Blinding Lights by The Weeknd")
        self.assertEqual(x["action"], "PLAY")
        self.assertEqual(x["query"], "Blinding Lights")
        self.assertEqual(x["artist"], "The Weeknd")

    def test_controls(self):
        self.assertEqual(self.brain.understand("play next")["action"], "NEXT")
        self.assertEqual(self.brain.understand("pause music")["action"], "PAUSE")
        self.assertEqual(self.brain.understand("previous")["action"], "PREVIOUS")

    def test_search(self):
        x = self.brain.understand("search Arijit Singh songs")
        self.assertEqual(x["action"], "SEARCH")
        self.assertEqual(x["query"], "Arijit Singh songs")

    def test_similar_without_current_is_safe(self):
        self.assertEqual(self.brain.understand("play something similar")["action"], "SIMILAR")

    def test_playlist_command(self):
        x = self.brain.understand("play my playlist Late Night")
        self.assertEqual(x["action"], "PLAYLIST")
        self.assertEqual(x["playlist_name"], "late night")


if __name__ == "__main__":
    unittest.main()
