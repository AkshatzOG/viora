import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.rag import grounded_insight, retrieve_context


class LocalRagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "viora.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_retrieval_grounds_insight_in_saved_taste_and_favorites(self):
        self.db.save_onboarding(["Artist One"], ["Ambient"], ["English"], ["Calm"], "explorer")
        self.db.set_favorite({"id":"track-1", "title":"Quiet Blue", "artist":"Artist One"}, True)
        context = retrieve_context("Quiet Blue", db=self.db)
        self.assertEqual(context["tracks"][0]["id"], "track-1")
        answer = grounded_insight("Why do you recommend music this way?", context)
        self.assertIn("Artist One", answer)
        self.assertIn("1 saved favorites", answer)


if __name__ == "__main__":
    unittest.main()
