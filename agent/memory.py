from __future__ import annotations

from dataclasses import dataclass, field
from core.database import get_db


@dataclass
class MusicMemory:
    current_song: dict | None = None
    current_artist: str | None = None
    active_genre: str | None = None
    active_language: str | None = None
    active_mood: str | None = None
    recently_played: list[str] = field(default_factory=list)
    conversation: list[dict] = field(default_factory=list)

    def remember_song(self, track):
        self.current_song = dict(track or {})
        self.current_artist = track.get("artist") or track.get("channel") if track else None
        title = track.get("title") if track else None
        if title:
            self.recently_played = (self.recently_played + [title])[-20:]

    def set_filters(self, genre=None, language=None, mood=None):
        if genre is not None: self.active_genre = genre
        if language is not None: self.active_language = language
        if mood is not None: self.active_mood = mood

    def clear_filters(self):
        self.active_genre = self.active_language = self.active_mood = None

    def add_message(self, role, content):
        self.conversation = (self.conversation + [{"role": role, "content": content}])[-20:]

    def context(self):
        db = get_db()
        onboarding = db.get_onboarding()
        return {
            "current_song": self.current_song,
            "current_artist": self.current_artist,
            "active_genre": self.active_genre,
            "active_language": self.active_language,
            "active_mood": self.active_mood,
            "recently_played": self.recently_played[-10:],
            "recent_conversation": self.conversation[-10:],
            "taste": onboarding,
        }
