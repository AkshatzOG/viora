from dataclasses import dataclass, field

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
        self.current_song = track
        self.current_artist = track.get("artist")
        title = track.get("title")
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
        return {
            "current_song": self.current_song,
            "current_artist": self.current_artist,
            "active_genre": self.active_genre,
            "active_language": self.active_language,
            "active_mood": self.active_mood,
            "recently_played": self.recently_played[-10:],
            "recent_conversation": self.conversation[-10:],
        }
