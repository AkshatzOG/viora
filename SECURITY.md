# Security policy

## Scope

Viora is designed to run on the user's own Windows machine. The default Flask bind is 127.0.0.1, so the web interface is local-only unless configuration is changed.

## Local data

Personalization, search history, playback history, playlists, theme preference, and download metadata are stored in SQLite under the configured local data directory. Keep .env, data/, downloads/, .runtime.json, virtual environments, and generated logs out of release archives and source control.

## Reporting

For a security issue, avoid publishing sensitive details in a public issue. Use the repository's private vulnerability-reporting mechanism when available.
