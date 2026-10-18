# Viora 15.8.4

## Provider playlist player and native playback fix

- Added recognizable service logos to saved Spotify, Apple Music, YouTube Music, Amazon Music, Tidal, Deezer, and SoundCloud playlist links.
- Added an in-app full-screen playlist player that updates Viora’s Now Playing panel and bottom player with the playlist name and service.
- Read Spotify and YouTube embed playback state through their official player APIs; added a manual listening status for services that do not expose embed playback state.
- Launch MPV using the configured MPV_PATH instead of depending on the executable also being on PATH.
- Retry a failed direct audio stream through its original source URL so MPV's yt-dlp hook can refresh or resolve it.
- Prefer an existing downloaded local file over an old stream URL when Viora plays or queues a saved track.
- Include actionable MPV startup/play errors in the playback response and bump the service-worker cache.

## Notes and limits

- Cross-origin provider embeds control their own audio. Playback-state reporting is available where the provider API exposes it; other services have a manual status control.
- Full-screen embedded playback requires internet access and remains subject to the provider’s account, region, browser, and embedding restrictions.

# Viora 15.8.3

## Header wordmark font

- Use the supplied Qurova Bold font for the header wordmark and display it as lowercase “viora”.
- Include the font in the source release and service-worker shell cache for browser/PWA use.

# Viora 15.8.2

## Full-screen color atmosphere

- Removed the oval beat-reactive outline from the full-screen player and replaced it with a soft, borderless glow.
- Expanded the dark-mode palette with purple, blue, cyan, teal, and green hues.
- Expanded the light-mode palette with orange, yellow, pink, and red hues.
- Bumped the service-worker cache so installed browser copies refresh the styling.

# Viora 15.8.1

## Saved service playlist visibility fix

- Return the saved playlist list and count from create, duplicate, edit, and delete operations so the page reflects the persisted state immediately.
- Show the saved-service playlist section near the top of the Playlists page.
- Replace the misleading initial zero with a loading state and a retry message if the saved list cannot be loaded.
- Bump the service-worker cache version so installed browser copies refresh the playlist UI.

## Playlist links and provider previews

- Replaced Spotify account authorization and Client ID setup with a permanent, editable collection of shared playlist links.
- Save, preview where supported, rename, update, and delete playlist links from Spotify, Apple Music, YouTube/YouTube Music, Amazon Music, Tidal, Deezer, and SoundCloud.
- Spotify, Apple Music, and YouTube links use their official embedded players. Other providers open in their own app or website.
- Saved links are stored in Viora's local SQLite settings and included in database backups.
- Clarified that cross-origin provider players do not expose playlist contents. Native Viora playlists can still be built from copied track names or CSV, M3U/M3U8, JSON, and text exports.

## Charts and player experience

- Put official chart sources first: Apple Music regional Top 50/100 data, official YouTube Music weekly songs and daily video charts, and Spotify Charts.
- Added on-device most-played and favorites charts. Personalized selections remain configurable from 3 to 12 cards.
- Added audio-reactive color waves driven by local loopback audio energy, bass, and beat analysis, with the existing user setting and reduced-motion control respected.
- Matched full-screen Now Playing colors to the selected Viora theme.
- Added a review step and back navigation to the first-run taste walkthrough.
- Improved song relevance and source-quality tie-breaking in search and Agent results; removed the “Matches for your request” heading.

## Notes and limits

- Viora no longer needs Spotify credentials. Provider previews depend on the provider, account, region, browser, and network.
- Viora does not sign in to external services or read private playlist contents. Import a track list/export to build a native Viora playlist.
- Apple Music rankings are provided by its regional feed; YouTube Music and Spotify chart cards open official chart pages. Viora's personal charts use only this device's local library.
- Native APK, signed Windows installer, hosted accounts, cross-device sync, and device-wide playback verification are not part of this source release.
