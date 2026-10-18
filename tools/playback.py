import threading
import time
import shutil
from collections import deque
from pathlib import Path

import numpy as np
import soundcard as sc

from python_mpv_jsonipc import MPV
from config import MPV_PATH, YTDLP_PATH, MAX_QUEUE_SIZE


class AudioAnalyzer:
    """Continuously analyzes Windows speaker loopback audio.

    Produces normalized values in the 0..1 range:
      - energy: overall RMS/loudness
      - beat: transient/low-frequency beat strength

    SoundCard uses the Windows WASAPI loopback device, so this analyzes the
    actual system output instead of the YouTube metadata or mpv clock.
    """

    SAMPLE_RATE = 44100
    BLOCK_SIZE = 2048
    HISTORY_SIZE = 43

    def __init__(self):
        self._lock = threading.RLock()
        self._energy = 0.0
        self._beat = 0.0
        self._bass = 0.0
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name="audio-analyzer",
            daemon=True,
        )
        self._thread.start()

    def values(self):
        with self._lock:
            return {
                "audio_energy": round(float(self._energy), 4),
                "audio_beat": round(float(self._beat), 4),
                "audio_bass": round(float(self._bass), 4),
            }

    def stop(self):
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    @staticmethod
    def _clip01(value):
        return float(np.clip(value, 0.0, 1.0))

    def _find_loopback(self):
        """Find the loopback microphone corresponding to the default speaker."""
        speaker = sc.default_speaker()
        microphones = sc.all_microphones(include_loopback=True)

        # Prefer an exact/default-speaker-related loopback.
        speaker_name = (getattr(speaker, "name", "") or "").lower()
        candidates = [
            mic for mic in microphones
            if getattr(mic, "isloopback", False)
        ]

        if not candidates:
            raise RuntimeError("No Windows WASAPI loopback device found.")

        for mic in candidates:
            mic_name = (getattr(mic, "name", "") or "").lower()
            if speaker_name and (
                speaker_name in mic_name or mic_name in speaker_name
            ):
                return mic

        # SoundCard's loopback enumeration normally returns the monitor for
        # the current output device. If matching fails, use the first loopback
        # rather than disabling the feature completely.
        return candidates[0]

    def _run(self):
        energy_history = deque(maxlen=self.HISTORY_SIZE)
        bass_history = deque(maxlen=self.HISTORY_SIZE)
        previous_bass = 0.0
        recorder = None

        try:
            loopback = self._find_loopback()
            print("[audio] Loopback:", getattr(loopback, "name", "unknown"))

            # Two or more channels avoids the known Windows/WASAPI single-
            # channel recording issue in SoundCard.
            channels = 2 if getattr(loopback, "channels", 2) != 1 else None

            recorder = loopback.recorder(
                samplerate=self.SAMPLE_RATE,
                channels=channels,
                blocksize=self.BLOCK_SIZE,
            )
            recorder.__enter__()

            print("[audio] Reactive analyzer started.")

            # Hann window reduces spectral leakage.
            window = np.hanning(self.BLOCK_SIZE).astype(np.float32)

            while self._running:
                data = recorder.record(numframes=self.BLOCK_SIZE)

                if data is None or len(data) < self.BLOCK_SIZE // 2:
                    continue

                data = np.asarray(data, dtype=np.float32)

                if data.ndim == 1:
                    mono = data
                else:
                    mono = np.mean(data, axis=1)

                # Remove DC offset and protect against NaN/Inf.
                mono = np.nan_to_num(mono, copy=False)
                mono = mono - np.mean(mono)

                rms = float(np.sqrt(np.mean(mono * mono) + 1e-12))

                # Spectral magnitude.
                sample = mono[-self.BLOCK_SIZE:]
                if len(sample) < self.BLOCK_SIZE:
                    sample = np.pad(
                        sample,
                        (self.BLOCK_SIZE - len(sample), 0),
                    )

                spectrum = np.abs(np.fft.rfft(sample * window))
                freqs = np.fft.rfftfreq(
                    self.BLOCK_SIZE,
                    1.0 / self.SAMPLE_RATE,
                )

                # Music-relevant bass band.
                bass_mask = (freqs >= 45) & (freqs <= 180)
                bass = float(
                    np.sqrt(
                        np.mean(
                            spectrum[bass_mask] ** 2
                        ) + 1e-12
                    )
                )

                energy_history.append(rms)
                bass_history.append(bass)

                # Adaptive loudness normalization.
                energy_ref = max(
                    np.percentile(energy_history, 90),
                    1e-4,
                )
                energy_floor = min(
                    np.percentile(energy_history, 20),
                    energy_ref * 0.45,
                )
                energy = (rms - energy_floor) / max(
                    energy_ref - energy_floor,
                    1e-5,
                )
                energy = self._clip01(energy)

                # Adaptive beat detection:
                # compare current bass energy against its recent median and
                # measure how sharply it increased from the previous frame.
                bass_ref = max(
                    np.median(bass_history),
                    1e-5,
                )
                bass_ratio = bass / bass_ref
                rise = max(
                    0.0,
                    (bass - previous_bass) / max(
                        previous_bass,
                        bass_ref * 0.25,
                        1e-5,
                    ),
                )

                beat = self._clip01(
                    max(
                        (bass_ratio - 1.15) / 1.75,
                        rise / 3.0,
                    )
                )

                # Smooth energy/bass, but keep beats punchy.
                with self._lock:
                    self._energy += (energy - self._energy) * 0.22
                    self._bass += (energy * 0.35 + beat * 0.65 - self._bass) * 0.28
                    self._beat = max(
                        beat,
                        self._beat * 0.68,
                    )

                previous_bass = bass

        except Exception as exc:
            print("[audio] Analyzer disabled:", repr(exc))

        finally:
            if recorder is not None:
                try:
                    recorder.__exit__(None, None, None)
                except Exception:
                    pass

            with self._lock:
                self._energy = 0.0
                self._beat = 0.0
                self._bass = 0.0

            print("[audio] Reactive analyzer stopped.")


class MusicPlayer:
    """Application-owned music queue with MPV used only as the audio engine.

    The important design rule is that MPV does *not* own the playlist anymore.
    The agent owns ``current_track``, ``_upcoming_tracks`` and ``history``.
    MPV is asked to play exactly one stream at a time.  This makes next,
    previous and automatic queue advancement deterministic.
    """

    def __init__(self):
        self.mpv = None
        self.now_playing = None
        self.current_track = None
        self._paused = False
        self._playing = False
        self._lock = threading.RLock()
        self.history = []
        self._upcoming_tracks = []
        self._closed = False
        self._ignore_end_events = 0
        self._preview_snapshot = None
        self._preview_timer = None
        self._is_preview = False
        self._last_error = None
        self.audio_analyzer = AudioAnalyzer()
        try:
            if not self._mpv_available():
                raise FileNotFoundError(f"MPV was not found at {MPV_PATH!r} or on PATH")
            self._start_mpv()
        except Exception as exc:
            self._last_error = str(exc)
            print("[player] MPV unavailable at startup:", repr(exc))
            self.mpv = None

    @staticmethod
    def _mpv_available():
        candidate = str(MPV_PATH or "").strip()
        return bool(candidate and (Path(candidate).is_file() or shutil.which(candidate)))

    def _start_mpv(self):
        if not self._mpv_available():
            raise FileNotFoundError(f"MPV was not found at {MPV_PATH!r} or on PATH")
        print("[player] Starting mpv...")
        print("[player] mpv:", MPV_PATH)
        print("[player] yt-dlp:", YTDLP_PATH)

        self.mpv = MPV(
            mpv_location=str(MPV_PATH),
            vid="no",
            idle="yes",
            ytdl_format="bestaudio/best",
            script_opts=f"ytdl_hook-ytdl_path={YTDLP_PATH}",
        )

        self.mpv.bind_event("file-loaded", self._on_loaded)
        self.mpv.bind_event("end-file", self._on_finished)

        self._closed = False
        self._last_error = None
        print("[player] mpv started successfully.")

    def _restart_mpv(self):
        print("[player] MPV connection lost; restarting...")
        try:
            self.mpv.terminate()
        except Exception:
            pass

        self._start_mpv()

        if self.current_track and not self._closed:
            url = self._play_url(self.current_track)
            if url:
                self._ignore_end_events += 1
                try:
                    self.mpv.command("loadfile", url, "replace")
                    self._playing = True
                except Exception as exc:
                    print("[player] MPV restart playback failed:", repr(exc))
                    self._ignore_end_events = max(0, self._ignore_end_events - 1)

    def _command(self, *args):
        with self._lock:
            try:
                if self.mpv is None:
                    self._start_mpv()
                return self.mpv.command(*args)
            except (BrokenPipeError, OSError):
                if self._closed or not self._mpv_available():
                    raise
                self._restart_mpv()
                return self.mpv.command(*args)

    def _get(self, name, default=None):
        try:
            value = self._command("get_property", name)
            return default if value is None else value
        except Exception:
            return default

    @staticmethod
    def _identity(track):
        track = track or {}
        return track.get("id") or track.get("watch_url") or track.get("title")

    @staticmethod
    def _play_url(track):
        track = track or {}
        local_path = track.get("local_path")
        if local_path:
            try:
                if Path(local_path).is_file():
                    return str(Path(local_path))
            except (OSError, TypeError, ValueError):
                pass
        return track.get("stream_url") or track.get("watch_url") or local_path

    def _remember_history(self, track):
        identity = self._identity(track)
        if not identity:
            return

        self.history = [
            item for item in self.history
            if self._identity(item) != identity
        ]
        self.history.append(dict(track))
        self.history = self.history[-50:]

    def _load_current(self, track, suppress_end=True):
        """Load exactly one track into MPV without touching application queue."""
        if not track:
            return False

        url = self._play_url(track)
        if not url:
            return False

        self.current_track = dict(track)
        self.now_playing = track.get("title") or "Unknown"
        self._paused = False
        self._playing = True
        self._last_error = None

        # loadfile replace causes an end-file(stop) event for the previous
        # MPV item. That event is not a real end of the application track.
        if suppress_end:
            self._ignore_end_events += 1
        try:
            self._command("loadfile", url, "replace")
        except Exception as exc:
            if suppress_end:
                self._ignore_end_events = max(0, self._ignore_end_events - 1)
            self._playing = False
            self._last_error = str(exc)
            self.current_track = None
            self.now_playing = None
            raise

        return True

    def _advance_to_next(self):
        """Move the application queue forward after EOF or Next."""
        with self._lock:
            if not self._upcoming_tracks:
                self._playing = False
                self._paused = False
                return False

            old = self.current_track
            if old:
                self._remember_history(old)

            next_track = self._upcoming_tracks.pop(0)
            print("[player] NEXT:", next_track.get("title", "Unknown"))
            return self._load_current(next_track, suppress_end=True)

    def _on_loaded(self, event):
        with self._lock:
            self._playing = True
            self._paused = False
            if self.current_track:
                self.now_playing = self.current_track.get("title") or self.now_playing

        print("[player] File loaded:", self.now_playing)

    def _on_finished(self, event):
        reason = (event or {}).get("reason") if isinstance(event, dict) else None

        with self._lock:
            if self._closed:
                return

            # Manual replacement (play/next/previous/restart) generates an
            # end-file event with reason=stop. Consume that event instead of
            # treating it as natural playback completion. Only consume the
            # marker for a real stop event so it can never swallow a later EOF.
            if reason == "stop" and self._ignore_end_events:
                self._ignore_end_events -= 1
                print("[player] Ignored transition end-file:", event)
                return

            if self._is_preview:
                self._playing = False
                return

            if reason in {"error", "quit", "stop"}:
                if reason == "error" and self.current_track and self.current_track.get("stream_url") and self.current_track.get("watch_url"):
                    fallback_track = dict(self.current_track)
                    fallback_track.pop("stream_url", None)
                    print("[player] Direct stream failed; retrying with the source URL:", fallback_track.get("title", "Unknown"))
                    try:
                        if self._load_current(fallback_track, suppress_end=True):
                            return
                    except Exception as exc:
                        print("[player] Source URL fallback failed:", repr(exc))
                self._playing = False
                if reason == "error":
                    detail = (event or {}).get("file_error") or (event or {}).get("error") if isinstance(event, dict) else None
                    self._last_error = str(detail or "MPV could not read or play this media stream.")
                    self.current_track = None
                    self.now_playing = None
                print("[player] Track stopped:", event)
                return

            if self.current_track:
                self._remember_history(self.current_track)

            print("[player] Track ended:", event)

            if self._upcoming_tracks:
                next_track = self._upcoming_tracks.pop(0)
                print("[player] AUTO NEXT:", next_track.get("title", "Unknown"))
                try:
                    self._load_current(next_track, suppress_end=False)
                except Exception as exc:
                    print("[player] Auto-next failed:", repr(exc))
                    self._playing = False
            else:
                self._playing = False
                self._paused = False

    def play(self, track, remember=True, preserve_queue=True):
        """Play immediately.

        By default an explicit PLAY does NOT destroy an existing queue. The
        current song becomes the new current track and the existing upcoming
        tracks remain after it. Use ``preserve_queue=False`` only when a true
        queue replacement is intended.
        """
        if not track:
            return False

        with self._lock:
            self._cancel_preview()
            old = self.current_track
            if remember and old and self._identity(old) != self._identity(track):
                self._remember_history(old)

            if not preserve_queue:
                self._upcoming_tracks.clear()

            print("[player] PLAY:", track.get("title", "Unknown"))
            try:
                return self._load_current(track)
            except Exception as exc:
                self._last_error = str(exc)
                print("[player] Play failed:", repr(exc))
                return False

    def _cancel_preview(self):
        if self._preview_timer:
            self._preview_timer.cancel()
            self._preview_timer = None
        self._preview_snapshot = None
        self._is_preview = False

    def preview(self, track, seconds=20):
        """Audition a track briefly, then restore the previous playback state."""
        if not track:
            return False
        with self._lock:
            self._cancel_preview()
            snapshot = None
            if self.current_track:
                snapshot = {
                    "track": dict(self.current_track),
                    "position": float(self._get("time-pos", 0) or 0),
                    "paused": bool(self._get("pause", self._paused)),
                }
            self._preview_snapshot = snapshot
            self._is_preview = True
            if not self._load_current(track, suppress_end=True):
                self._cancel_preview()
                return False
            timer = threading.Timer(max(1, float(seconds)), self._restore_preview)
            timer.daemon = True
            self._preview_timer = timer
            timer.start()
            return True

    def _restore_preview(self):
        with self._lock:
            snapshot = self._preview_snapshot
            self._preview_timer = None
            self._preview_snapshot = None
            if snapshot:
                self._is_preview = False
                if self._load_current(snapshot["track"], suppress_end=True):
                    try:
                        self._command("seek", snapshot["position"], "absolute")
                        self._command("set", "pause", "yes" if snapshot["paused"] else "no")
                        self._paused = snapshot["paused"]
                        self._playing = True
                    except Exception as exc:
                        print("[player] Preview restore position failed:", repr(exc))
            else:
                self._is_preview = False
                try:
                    self._command("stop")
                except Exception:
                    pass
                self.current_track = None
                self.now_playing = None
                self._playing = False
                self._paused = False

    def queue(self, tracks):
        """Add already-prepared tracks to the application queue.

        MPV is intentionally not touched here. The tracks are already resolved
        by the YouTube layer, so they are ready for instant playback later.
        """
        tracks = list(tracks or [])
        if not tracks:
            return False

        with self._lock:
            remaining = max(0, MAX_QUEUE_SIZE - len(self._upcoming_tracks))
            if remaining <= 0:
                return False

            existing = {self._identity(t) for t in self._upcoming_tracks}
            current_id = self._identity(self.current_track)
            added = 0

            for track in tracks[:remaining]:
                identity = self._identity(track)
                if not identity or identity in existing or identity == current_id:
                    continue

                url = self._play_url(track)
                if not url:
                    continue

                print("[player] QUEUE:", track.get("title", "Unknown"))
                self._upcoming_tracks.append(dict(track))
                existing.add(identity)
                added += 1

            return added > 0

    def pause(self):
        self._command("set", "pause", "yes")
        self._paused = True
        return True

    def resume(self):
        self._command("set", "pause", "no")
        self._paused = False
        self._playing = True
        return True

    def toggle_pause(self):
        paused = bool(self._get("pause", self._paused))
        return self.resume() if paused else self.pause()

    def next(self):
        """Skip to the next application-queue track."""
        with self._lock:
            self._cancel_preview()
        return self._advance_to_next()

    def previous(self):
        """Go back one track while preserving the upcoming queue."""
        with self._lock:
            self._cancel_preview()
            if not self.history:
                return False

            current = self.current_track
            previous = self.history.pop()

            if current and self._identity(current) != self._identity(previous):
                self._upcoming_tracks.insert(0, dict(current))

            print("[player] PREVIOUS:", previous.get("title", "Unknown"))
            try:
                return self._load_current(previous, suppress_end=True)
            except Exception as exc:
                print("[player] Previous failed:", repr(exc))
                return False

    def play_queue_item(self, index):
        """Play a specific item from the upcoming queue.

        The selected item is removed from the queue and becomes current.
        The old current track is moved into history, while every other
        upcoming item stays in the same order.
        """
        with self._lock:
            self._cancel_preview()
            try:
                index = int(index)
            except (TypeError, ValueError):
                return False

            if index < 0 or index >= len(self._upcoming_tracks):
                return False

            selected = self._upcoming_tracks.pop(index)
            old = self.current_track

            if old and self._identity(old) != self._identity(selected):
                self._remember_history(old)

            print("[player] QUEUE SELECT:", selected.get("title", "Unknown"))

            try:
                return self._load_current(selected, suppress_end=True)
            except Exception as exc:
                # Put the selected item back at its original location if
                # loading failed, so a failed click never destroys the queue.
                self._upcoming_tracks.insert(index, selected)
                print("[player] Queue selection failed:", repr(exc))
                return False

    def shuffle_queue(self):
        import random
        with self._lock:
            random.shuffle(self._upcoming_tracks)
        return True

    def clear_queue(self):
        with self._lock:
            self._upcoming_tracks.clear()
        return True

    def remove_queue_item(self, index):
        with self._lock:
            try:
                index = int(index)
            except (TypeError, ValueError):
                return False
            if index < 0 or index >= len(self._upcoming_tracks):
                return False
            self._upcoming_tracks.pop(index)
            return True

    def filter_queue(self, predicate):
        with self._lock:
            before = len(self._upcoming_tracks)
            self._upcoming_tracks = [track for track in self._upcoming_tracks if predicate(track)]
            return before - len(self._upcoming_tracks)

    def stop(self, clear_queue=True):
        with self._lock:
            self._cancel_preview()
            if clear_queue:
                self._upcoming_tracks.clear()
            try:
                self._command("stop")
            except Exception:
                pass
            self.current_track = None
            self.now_playing = None
            self._playing = False
            self._paused = False
        return True

    def filter_queue(self, predicate):
        with self._lock:
            before = len(self._upcoming_tracks)
            self._upcoming_tracks = [track for track in self._upcoming_tracks if predicate(track)]
            return before - len(self._upcoming_tracks)

    def stop(self, clear_queue=True):
        with self._lock:
            self._cancel_preview()
            if clear_queue:
                self._upcoming_tracks.clear()
            try:
                self._command("stop")
            except Exception:
                pass
            self.current_track = None
            self.now_playing = None
            self._playing = False
            self._paused = False
        return True

    def status(self):
        duration = self._get("duration", 0) or 0
        time_pos = self._get("time-pos", 0) or 0

        with self._lock:
            title = self.current_track.get("title") if self.current_track else self.now_playing
            if title:
                self.now_playing = title

            thumbnail = self.current_track.get("thumbnail") if self.current_track else None
            queue_length = len(self._upcoming_tracks)
            paused = bool(self._get("pause", self._paused))
            playing = bool(self._playing)
            history_length = len(self.history)

            status = {
                "now_playing": self.now_playing if playing or self.current_track else None,
                "thumbnail": thumbnail if playing or self.current_track else None,
                "current_track": dict(self.current_track) if self.current_track else None,
                "queue_length": queue_length,
                "playlist_count": (1 + queue_length) if self.current_track else 0,
                "playlist_position": history_length if self.current_track else -1,
                "paused": paused,
                "playing": playing,
                "duration": duration,
                "time_pos": time_pos,
                "history_length": history_length,
                "queued_tracks": [dict(t) for t in self._upcoming_tracks[:MAX_QUEUE_SIZE]],
                "player_ready": self.mpv is not None,
                "player_error": self._last_error,
            }

        status.update(self.audio_analyzer.values())
        return status

    def close(self):
        with self._lock:
            self._cancel_preview()
            self._closed = True
            self._playing = False

        try:
            self.audio_analyzer.stop()
        except Exception as exc:
            print("[audio] analyzer close:", repr(exc))
            try:
                if self.mpv is not None:
                    self.mpv.command("quit")
            except Exception:
                pass
            try:
                if self.mpv is not None:
                    self.mpv.terminate()
            except Exception:
                pass


player = MusicPlayer()
