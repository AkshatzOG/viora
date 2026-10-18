# Viora roadmap and release checklist

Status is based on the source code in this release. Items marked “needs device verification” exist in source but are not certified across all Windows, Android, and browser configurations.

## v15.8.4 — service playlist player and MPV startup

- [x] Show provider logos and add an in-app full-screen player for saved service playlists.
- [x] Reflect Spotify and YouTube playlist playback in Viora Now Playing and offer a manual status fallback for providers without embed state events.
- [x] Pass the configured MPV executable path to the MPV launcher and prioritize existing local files for offline playback.
- [x] Surface MPV playback errors in the UI and refresh installed browser/PWA caches.
- [ ] Verify MPV playback on the user's Windows installation and service embeds across target browsers.

## v15.8.3 — header wordmark font

- [x] Use the supplied Qurova Bold font for the header wordmark and display “viora” in lowercase.
- [x] Include the font in source releases and the service-worker shell cache.

## v15.8.2 — full-screen color atmosphere

- [x] Remove the oval beat-reactive outline from the full-screen player and use a soft glow instead.
- [x] Add more cool hues to dark mode and warm hues to light mode.
- [x] Bump the app and service-worker versions so browser installs refresh the CSS.

## v15.8.1 — saved service playlist visibility fix

- [x] Return the persisted playlist collection after every save, edit, and delete, and render that response immediately.
- [x] Move the saved service playlist section directly below the Playlists page introduction and show a loading state instead of a temporary zero count.
- [x] Bump the PWA cache so installed copies fetch the updated playlist code.

## v15.8 — provider playlists, official charts, and listening atmosphere

- [x] Removed Spotify Client ID and account authorization setup. No service credentials are needed for playlist links.
- [x] Added a permanent Playlists section for shared links from Spotify, Apple Music, YouTube/YouTube Music, Amazon Music, Tidal, Deezer, and SoundCloud, with add, preview, edit, and delete actions.
- [x] Use official embeds where supported and external links otherwise; explain that cross-origin players do not expose playlist track lists.
- [x] Added official Apple Music Top 50/100, YouTube Music weekly songs/daily videos, and Spotify chart choices, plus local Viora listening charts.
- [x] Kept chart choices customizable from 3 to 12 cards and labeled Viora search mixes separately from measured charts.
- [x] Added live audio-reactive ambient gradients driven by system loopback audio; the user setting and reduced-motion preference control the effect.
- [x] Matched full-screen Now Playing to the main app's dark or warm-light theme.
- [x] Added a review step and back navigation to taste onboarding; refined query relevance and source-quality ordering and removed the Agent's “Matches for your request” label.
- [ ] Verify provider embeds and the audio-reactive analyzer on supported Windows output devices and mobile browsers.

## v15.7 — mobile usability, charts, queue, and playlist import

- [x] Queue page shows Now Playing and upcoming songs, with play, remove, shuffle, save as playlist, and clear actions.
- [x] Added Spotify playlist preview and playlist-file import foundations; saved provider links are now handled by the v15.8 collection.
- [x] Expanded Charts to 27 selectable cards, with persistent selection of 3–12 charts and six additional original card artworks.
- [x] Mix charts load directly without waiting for the separate Apple Music regional feed.
- [x] Restore/backup controls wrap cleanly, with mobile-friendly spacing.
- [x] Added Space, Left Arrow, and Right Arrow playback shortcuts, with text-field focus protection.
- [x] Added mobile browser and PWA layout rules, ambient gradient waves while idle and during playback, and compact loading feedback for search and playback.
- [x] Added the supplied home screenshot, complete GitHub README, and MIT License.
- [ ] Verify the interface and playback on physical Android and iOS devices.

## v15.0 — Discovery foundation

- [x] Discovery-first Home with recommendations, continue-listening shelf, mood entry points, downloaded library, and playlists.
- [x] First-run taste onboarding for artists, genres, languages, moods, and familiar/explorer preference; profile can be edited later.
- [x] Unified local-library and online music search.
- [x] Player controls, queue, favorites, 20-second preview, and local-first playback of downloaded files.
- [x] Natural-language commands for playback, search, queue, playlists, favorites, and downloads.

## v15.1 — SQLite foundation

- [x] SQLite persistence for tracks, settings, favorites, play events, taste profile, search history, playlists, and download metadata.
- [x] History survives restarts and counts repeated plays for listening signals.
- [x] History screen shows the latest entry once per normalized title and artist; play-event analytics remain available.
- [x] SQLite online backup and validated restore, including Agent conversation and settings.

## v15.2 — Playlists, themes, and source ordering

- [x] Create, rename, delete, add/remove, reorder, sort, play, shuffle, and save queue as playlist.
- [x] Warm yellow/pink light theme, deep dark theme, persistent settings, and animated moon/sun control.
- [x] Official/likely artist or label source group shown above community-upload results.
- [x] Source badges indicate the level of local confidence.

## v15.3 — Local library and downloads

- [x] Optional track download, local library, offline badge, local playback, and missing-file detection.
- [x] Download folder selection and storage usage display.
- [x] Streaming/search remains the normal path; downloads are user initiated.

## v15.4 — Offline mode

- [x] Auto, Online, and Offline playback modes.
- [x] Local search and playback when Offline is selected; nonlocal play, queue, preview, download, and online search are blocked.
- [x] Browser connectivity is sent to the local service so Auto mode stops starting online searches after a browser offline event.
- [x] Offline recommendations and Agent trend requests are restricted to matching local files.
- [ ] Verify disconnect/reconnect and MPV queue behavior across several Windows network adapters.

## v15.5 — Taste, recommendations, and Agent

- [x] Local recommendation scoring incorporates taste, listening behavior, favorites, skips/completion, recency, and novelty/diversity signals.
- [x] Played tracks are filtered from new recommendations by default; the control is user-adjustable.
- [x] Agent retrieves local tracks/history/favorites/profile for grounded answers and uses retrieved search tracks for music requests.
- [x] Agent playlist creation uses resolved tracks rather than invented song names.
- [x] Main search and Agent result sources are separated so an unrelated local retrieval result is not shown as a match.
- [x] Narrow trend requests retain their subject and return no result when relevant candidates are absent.
- [x] Dynamic status refresh invalidates Continue Listening and refreshes History when the current song changes.
- [ ] Optional local LLM; current Agent is deterministic and retrieval-grounded, not a generative model.
- [ ] YouTube API-based channel ownership/verification; current source classification is heuristic and cannot guarantee canonical versions.

## v15.6 — UI, data portability, and discovery

- [x] Home, Discover, Search, Agent, Artists, Charts, Playlists, Queue, Favorites, History, Offline Library, and Settings navigation.
- [x] Wider Agent conversation layout avoids the nested clipped/horizontal-scroll pane from the supplied screenshot.
- [x] Play, queue, favorite, save-to-playlist, download, and preview actions across discovery cards and library rows; current player and queue also have playlist actions.
- [x] Queue empty state with links to Discover, Search, and playlist creation.
- [x] Idle Now Playing placeholder, hidden when a track is active.
- [x] Optional beat/color reactive background and reduced-motion setting.
- [x] Curated worldwide artist starter list (roughly 80 artists), artist photos loaded from Wikipedia page thumbnails when online, and user artists learned from listening history. The listening map only appears when there is at least one play.
- [x] Regional Apple Music Charts page with source links and Viora search actions, animated original card art, country Top 50, daily refresh, and customizable 3–12 card shelves from 27 options.
- [x] Love, Pop, English, Hindi, Phonk, Hip-hop, Afrobeats, K-pop, J-pop, Workout, Chill, Focus, Dance, Indie, Rock, R&B, Latin, Country, Jazz, Metal, Acoustic, Devotional, Punjabi, Electronic, and Throwbacks discovery mixes with likely-official source signals ranked first. These are Viora search mixes, not measured platform charts.
- [x] Popular-this-week card backed by the current regional most-played feed; refreshes daily and discloses that the source does not publish exact weekly play totals.
- [x] Background import with progress for CSV, M3U/M3U8, JSON, and text playlists, plus pasted track lists.
- [x] Spotify playlist preview through the official embed; the cross-origin player does not expose its item list.
- [x] Settings backup/restore for profile and library state; offline audio folder is documented as a separate copy.
- [x] Community Telegram link, close/shutdown action, mobile-responsive navigation, PWA shell, and install control.
- [x] Remove release version label from the product UI; release metadata stays in `VERSION`.
- [x] Bottom-player idle state, Stop current song action, and full-screen Now Playing.
- [x] Distinct Viora Agent mark and refreshed product tagline.
- [x] Space toggles play/pause and arrow keys skip tracks; shortcuts ignore text fields and controls.
- [ ] Verify keyboard navigation, screen-reader labels, focus states, and touch targets on real device sizes.
- [ ] Finish bulk library editing and richer playlist collaboration/sharing.
- [ ] Exact weekly play-count charts. The current Apple Music feed is a daily regional most-played snapshot and does not provide historical weekly totals.
- [ ] More chart providers and a true worldwide live ranking feed. Current page is a region-specific Apple Music chart snapshot, not Spotify's private/user-specific artist ranking API.

## Packaging and release readiness

- [x] PWA manifest and local install flow; hosted PWA instructions require HTTPS.
- [x] Responsive mobile web layout and installable PWA controls.
- [x] Windows PyInstaller build script can copy MPV/yt-dlp binaries from the build machine when present.
- [ ] Build and sign the actual Windows `.exe` app folder on a clean Windows machine and verify the bundled MPV dependencies.
- [ ] Native Android APK/TWA build, signing, and device tests. Requires an owned HTTPS domain, Digital Asset Links, Android build tools, signing key, and the intended package/application id.
- [ ] Hosted website and automatic account/data sync. This build is local-first and does not create cloud accounts.
- [ ] Replace/obtain a redistributable brand font before a public/commercial release; the user-supplied Surgena font is marked Personal use only and is omitted from the release ZIP.
- [ ] Confirm third-party license notices and source availability before redistributing bundled MPV/yt-dlp binaries.
- [ ] Add and run a release QA matrix for MPV presence/absence, online/offline transition, PWA update, library restore, playlists, and representative search queries.

## Product direction and research notes

Viora adapts common music-app patterns—personalized shelves, quick actions, playlists, favorites, offline storage, and artist-driven discovery—using its own layout and identity. It does not copy protected branding or claim a Spotify catalog/API it does not have. Apple provides public regional chart RSS feeds that Viora can attribute directly; other chart cards link to their official providers.

- [Spotify: save music and podcasts with the plus button](https://newsroom.spotify.com/2023-02-27/save-your-favorite-songs-podcasts-and-more-with-spotifys-plus-button/)
- [Spotify: Home previews and quick actions](https://newsroom.spotify.com/2023-03-08/spotify-previews-clips-music-podcasts-audiobooks-home-feed/)
- [Apple Music RSS feed generator](https://performance-partners.apple.com/tools)
- [Apple Music API charts](https://developer.apple.com/documentation/applemusicapi/charts)
- [YouTube Music official charts](https://support.google.com/youtube/answer/9014376?hl=en-EN-5)
- [Apple Music favorites](https://support.apple.com/en-us/111118)
- [YouTube Music downloads and storage](https://support.google.com/youtubemusic/answer/6313535)
- [Android Trusted Web Activity guide](https://developer.android.com/develop/ui/views/layout/webapps/guide-trusted-web-activities-version2)
- [Wikimedia Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)
