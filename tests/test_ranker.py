import unittest

from tools.ranker import rank_tracks, remove_duplicates


class RankerTests(unittest.TestCase):
    def test_same_title_from_different_sources_survives_deduplication(self):
        tracks = [
            {"id": "fan", "title": "Blue Song", "channel": "A Fan Channel"},
            {"id": "artist", "title": "Blue Song", "channel": "Blue Artist - Topic"},
        ]
        result = remove_duplicates(tracks)
        self.assertEqual([track["id"] for track in result], ["fan", "artist"])

    def test_source_confidence_tiers_precede_relevance(self):
        tracks = [
            {"id": "community", "title": "Blue Song", "channel": "A Fan Channel"},
            {"id": "likely", "title": "Blue Song Official Audio", "channel": "Blue Artist - Topic"},
            {"id": "verified", "title": "Blue Song", "channel": "Blue Artist", "verified": True},
        ]
        result = rank_tracks(tracks, query="Blue Song", limit=3, prefer_tracks=True)
        self.assertEqual([track["id"] for track in result], ["verified", "likely", "community"])
        self.assertEqual(result[0]["source_category"], "official")
        self.assertEqual(result[1]["source_category"], "likely_official")
        self.assertEqual(result[2]["source_category"], "community")


if __name__ == "__main__":
    unittest.main()
