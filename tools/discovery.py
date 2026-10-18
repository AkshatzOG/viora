"""Local discovery compatibility layer. No Ollama or remote decision model."""
from core.recommender import similar_to


def recommend_similar(current_song, current_artist, count, user_text=""):
    track = {"title": current_song, "artist": current_artist}
    return similar_to(track, count)


def discover_current(query, count=5):
    from tools.youtube import discover_current as _discover_current
    return _discover_current(query, count, "MUSIC")
