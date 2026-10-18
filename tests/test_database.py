import tempfile
import unittest
from pathlib import Path
from core.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "library.db")
        self.track = {"id":"yt:demo","title":"Demo Song","artist":"Demo Artist","channel":"Demo Artist"}

    def tearDown(self):
        self.db.close(); self.tmp.cleanup()

    def test_onboarding_and_playlist(self):
        self.assertFalse(self.db.get_onboarding()["completed"])
        self.db.save_onboarding(["Demo Artist"],["Pop"],["English"],["Chill"],"balanced")
        self.assertTrue(self.db.get_onboarding()["completed"])
        pid=self.db.playlist_create("Test")
        self.db.playlist_add(pid,self.track)
        self.assertEqual(len(self.db.playlist_get(pid)["tracks"]),1)

    def test_favorite_and_history(self):
        self.db.set_favorite(self.track,True)
        self.assertEqual(self.db.list_tracks(favorites_only=True)[0]["is_favorite"],1)
        hid=self.db.record_play_start(self.track)
        self.db.record_play_end(hid,200,100)
        self.assertEqual(len(self.db.history()),1)


if __name__ == "__main__":
    unittest.main()
