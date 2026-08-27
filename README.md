**# Local Music Agent**

\> A local-first AI music and podcast agent that lets you control YouTube-powered playback with natural language.

Local Music Agent combines **\*\*Ollama\*\***, **\*\*YouTube/yt-dlp\*\***, **\*\*mpv\*\***, and a lightweight **\*\*Flask web UI\*\*** into one desktop-friendly application. The goal is simple: talk to your computer naturally and let the agent figure out what you mean.

Examples:

\`\`\`text

play Blinding Lights by The Weeknd

queue 5 phonk songs

play something chill

play something similar

play a podcast about AI

play a podcast by Raj Shamani

next

previous

pause

resume

\`\`\`

The project is designed for local Windows use, with a one-click \`.vbs\` launcher so the usual \`ollama serve\`, mpv, and Flask startup commands do not need to be entered manually.

**---**

**## Features**

**### Natural-language music control**

The agent understands common requests such as:

\- Exact song requests

\- Artist + song requests

\- Variants such as:

  - slowed

  - reverb

  - remix

  - acoustic

  - live

\- Genre requests

\- Mood requests

\- Queue requests

\- Similar-song requests

\- Playback controls

\- Podcast requests

Examples:

\`\`\`text

play Attention Charlie Puth

play Valam Aavo Ne

play Blinding Lights slowed

queue 3 phonk songs

play something chill

play something similar

play a podcast about AI

\`\`\`

**### YouTube-aware search and ranking**

Search results are not blindly accepted.

The search/ranking layer considers:

\- title relevance

\- artist/channel relevance

\- exact token overlap

\- fuzzy token matching

\- official audio/video signals

\- content type

\- duplicate removal

\- irrelevant educational/search-bait results

\- playlists, compilations and long mixes

\- lyrics/reaction/tutorial-style results

\- requested variants

It also tolerates small spelling or transliteration differences. For example, a request such as:

\`\`\`text

play valom avo ne

\`\`\`

can resolve to:

\`\`\`text

Valam Aavo Ne

\`\`\`

The system intentionally allows useful alternate versions such as slowed/reverb or other variants when they are relevant to the request.

**### Similar-song discovery**

When the user says:

\`\`\`text

play something similar

\`\`\`

the agent uses the current track as context rather than treating the phrase as a standalone YouTube search.

The system also filters common false positives such as:

\- "similar words"

\- "similar meaning"

\- English grammar lessons

\- mathematics/geometry explanations

\- educational videos

\- unrelated videos containing the word "similar"

**### Queue management**

The player supports:

\- queueing multiple tracks

\- next

\- previous

\- pause/resume

\- selecting queued tracks

\- queue thumbnails

\- persistent playback history/context

The queue is maintained independently from a newly requested song, so manually playing another track does not inherently destroy the existing queue.

**### Podcast mode**

The same natural-language interface can be used for podcasts and spoken content.

Examples:

\`\`\`text

play a podcast about AI

play a podcast by Raj Shamani

queue 3 podcasts about technology

\`\`\`

Podcast discovery uses different ranking signals from ordinary music searches so that episode/interview content can be preferred when the user explicitly asks for a podcast.

**### Rich local web interface**

The Flask UI provides:

\- natural-language chat

\- current track display

\- YouTube thumbnail/artwork

\- playback state

\- elapsed/total time

\- progress bar

\- queue list

\- queued-track thumbnails

\- queue position

\- playback history count

\- Previous / Pause / Resume / Next controls

\- filter clearing

\- one-click Close control

\- dynamic visual background

The interface is intentionally local and lightweight.

**### One-click Windows startup**

The repository includes Windows launcher scripts:

\`\`\`text

START\_LOCAL\_MUSIC\_AGENT.vbs

STOP\_LOCAL\_MUSIC\_AGENT.vbs

\`\`\`

The startup workflow is intended to handle the local services required by the application so you do not have to manually open several terminals.

**---**

**## Architecture**

\`\`\`text

User

  │

  ▼

Flask Web UI

  │

  ▼

Agent Router

  │

  ├── Fast deterministic intent parsing

  │

  └── Ollama fallback for ambiguous requests

  │

  ▼

Music / Podcast Discovery

  │

  ├── YouTube search

  ├── yt-dlp metadata

  ├── result filtering

  ├── relevance scoring

  ├── fuzzy matching

  └── duplicate removal

  │

  ▼

Playback Engine

  │

  └── mpv

\`\`\`

**### Main components**

\| Component | Purpose |

\|---|---|

\| \`app.py\` | Flask application and HTTP API |

\| \`agent/\` | Natural-language understanding, routing and conversation state |

\| \`tools/youtube.py\` | YouTube search/discovery |

\| \`tools/ranker.py\` | Search-result scoring and filtering |

\| \`tools/discovery.py\` | Similar-track and discovery logic |

\| \`tools/playback.py\` | mpv playback, queue and navigation |

\| \`templates/\` | Web UI |

\| \`config.py\` | Local configuration |

\| \`launcher.py\` | Local service startup/orchestration |

\| \`START\_LOCAL\_MUSIC\_AGENT.vbs\` | One-click Windows startup |

\| \`STOP\_LOCAL\_MUSIC\_AGENT.vbs\` | Windows shutdown helper |

\| \`check\_install.py\` | Installation/environment checks |

**---**

**## Requirements**

**### Operating system**

The current one-click launcher workflow targets:

\- Windows 10/11

\- Python 3.11+ recommended

\- PowerShell

\- mpv

\- yt-dlp

\- Ollama

The application itself is local and normally runs on:

\`\`\`text

http\://127.0.0.1:8888

\`\`\`

**### Python dependencies**

Install the dependencies from:

\`\`\`text

requirements.txt

\`\`\`

Recommended setup:

\`\`\`powershell

python -m venv venv

.env\Scripts\Activate.ps1

pip install -r requirements.txt

\`\`\`

**### Ollama**

Install Ollama separately and make sure the model configured by the project is available locally.

The application uses Ollama for ambiguous natural-language understanding, while deterministic commands can be handled locally without requiring an LLM round-trip.

This is intentional: common commands should be fast, while Ollama is used where language understanding actually adds value.

**### mpv**

Install mpv and configure its path through the project's configuration.

The playback layer uses mpv for actual media playback.

**### yt-dlp**

Install/download yt-dlp and configure its path.

yt-dlp is used for YouTube discovery/metadata and allows mpv to resolve YouTube media.

**---**

**## Installation — Windows 10/11

This section is for anyone cloning the project from GitHub onto a new Windows PC.

The repository contains the application source code and launcher scripts, but it does **not** bundle Python, Ollama, mpv, or yt-dlp. Those dependencies must be installed separately.

### 1. Install Git

Install Git for Windows, then verify:

```powershell
git --version
```

### 2. Install Python

Install **Python 3.11 or newer**.

During installation, enable **Add Python to PATH** and make sure `pip` is installed.

Verify:

```powershell
python --version
pip --version
```

### 3. Clone the repository

```powershell
cd C:\Projects
git clone https://github.com/YOUR_USERNAME/local-music-agent.git
cd local-music-agent
```

Replace `YOUR_USERNAME` with the GitHub account that owns the repository.

### 4. Create the Python environment

```powershell
python -m venv venv
```

Activate it:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify the important packages:

```powershell
python -c "import flask, requests; print('Python dependencies OK')"
```

### 5. Install Ollama

Install Ollama for Windows from the official Ollama website:

https://ollama.com/download/windows

Verify:

```powershell
ollama --version
```

The agent uses Ollama locally for requests that need additional natural-language understanding.

Check `config.py` and `.env.example` to see which model the project expects. If it is not installed:

```powershell
ollama pull MODEL_NAME
```

Replace `MODEL_NAME` with the model specified by the project configuration.

For normal use, you should **not** have to manually keep `ollama serve` running. `START_LOCAL_MUSIC_AGENT.vbs` is intended to start the required local services.

### 6. Install mpv

Download a Windows build of **mpv** and extract it.

The default project configuration can use:

```text
C:\mpv\
└── mpv.exe
```

Verify:

```powershell
Test-Path C:\mpv\mpv.exe
```

If you install it somewhere else, update the mpv path in the project's configuration.

### 7. Install yt-dlp

Download the Windows executable of **yt-dlp** and place it alongside mpv:

```text
C:\mpv\
├── mpv.exe
└── yt-dlp.exe
```

Verify:

```powershell
Test-Path C:\mpv\yt-dlp.exe
C:\mpv\yt-dlp.exe --version
```

yt-dlp is used for YouTube search/metadata and for resolving YouTube media for playback.

### 8. Configure the project

Check:

```text
config.py
.env.example
```

If the project uses `.env`, create your local file:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with values appropriate for the computer.

**Do not commit the real `.env` to GitHub.**

Machine-specific paths matter. For example, another computer may have:

```text
D:\Apps\mpv\mpv.exe
D:\Apps\mpv\yt-dlp.exe
```

instead of:

```text
C:\mpv\mpv.exe
C:\mpv\yt-dlp.exe
```

### 9. Run the installation checker

If `check_install.py` is present:

```powershell
.\venv\Scripts\python.exe check_install.py
```

Fix any missing dependency or executable path reported by the checker.

### 10. Start with one click

For normal Windows use, double-click:

```text
START_LOCAL_MUSIC_AGENT.vbs
```

The intended workflow is:

```text
START_LOCAL_MUSIC_AGENT.vbs
        ↓
start required local services
        ↓
start Flask application
        ↓
start mpv
        ↓
open the web interface
```

The web application normally runs at:

```text
http://127.0.0.1:8888
```

You should not need to manually open several terminals for normal use.

### 11. Stop everything

Use:

```text
STOP_LOCAL_MUSIC_AGENT.vbs
```

or the **Close** button in the web application.

The managed shutdown workflow is intended to stop the Local Music Agent and the services/processes started by the launcher.

### Manual troubleshooting

If the one-click launcher fails, run components manually to identify the problem.

Activate the environment:

```powershell
cd C:\Projects\local-music-agent
.\venv\Scripts\Activate.ps1
```

Check Ollama:

```powershell
ollama list
```

Check the Ollama API:

```powershell
python -c "import requests; print(requests.get('http://127.0.0.1:11434/api/tags').status_code)"
```

A working local Ollama API should return:

```text
200
```

For debugging only, Ollama can be started manually:

```powershell
ollama serve
```

Keep that terminal open while testing. `Ctrl+C` stops the Ollama server.

Check mpv:

```powershell
C:\mpv\mpv.exe --version
```

Check yt-dlp:

```powershell
C:\mpv\yt-dlp.exe --version
```

Then run the Flask application:

```powershell
.\venv\Scripts\python.exe app.py
```

Open:

```text
http://127.0.0.1:8888
```

### Common installation problems

#### `ModuleNotFoundError`

Example:

```text
ModuleNotFoundError: No module named 'requests'
```

Make sure the virtual environment is active:

```powershell
.\venv\Scripts\Activate.ps1
```

Then:

```powershell
pip install -r requirements.txt
```

#### Ollama connection refused

Example:

```text
ConnectionRefusedError: [WinError 10061]
```

Ollama is not currently listening on port `11434`.

Check:

```powershell
python -c "import requests; print(requests.get('http://127.0.0.1:11434/api/tags').status_code)"
```

For debugging:

```powershell
ollama serve
```

#### mpv `BrokenPipeError` / `handle is closed`

The mpv process or its IPC connection has stopped.

Verify:

```powershell
Test-Path C:\mpv\mpv.exe
```

Then restart the application with:

```text
START_LOCAL_MUSIC_AGENT.vbs
```

#### Port 8888 already in use

Check:

```powershell
netstat -ano | findstr :8888
```

Identify a process:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = PID"
```

Replace `PID` with the process ID shown by `netstat`.

Do not start a second copy if an existing Local Music Agent instance is already listening on port `8888`.

---

## Configuration**

Create your local environment from:

\`\`\`text

.env.example

\`\`\`

Do **\*\*not\*\*** commit your real \`.env\`.

Typical configuration includes the local Ollama endpoint/model and application port.

The default web application port is:

\`\`\`text

8888

\`\`\`

**---**

**## Running**

**### Recommended: Windows one-click startup**

Double-click:

\`\`\`text

START\_LOCAL\_MUSIC\_AGENT.vbs

\`\`\`

This is the preferred desktop workflow.

It should start the local application and its required services, then open the web interface.

**### Manual development startup**

For development/debugging, you can run the Flask application directly:

\`\`\`powershell

.env\Scripts\python.exe app.py

\`\`\`

Then open:

\`\`\`text

http\://127.0.0.1:8888

\`\`\`

For normal use, prefer the VBS launcher.

**---**

**## Stopping the application**

Use:

\`\`\`text

STOP\_LOCAL\_MUSIC\_AGENT.vbs

\`\`\`

or the **\*\*Close\*\*** button inside the web application.

The Close workflow is intended to stop the local agent and its managed playback/service processes together.

**---**

**## HTTP API**

The Flask application exposes local endpoints including:

\`\`\`text

GET  /

POST /command

POST /pause

POST /resume

POST /toggle-pause

POST /next

POST /previous

POST /queue/play/\<index>

GET  /status

GET  /context

POST /clear-filter

POST /shutdown

GET  /health

\`\`\`

**### Example command request**

\`\`\`http

POST /command

Content-Type: application/json

{

  "text": "play Blinding Lights by The Weeknd"

}

\`\`\`

The response contains the agent reply and current player status.

**### Playback navigation**

The UI controls use dedicated endpoints:

\`\`\`text

POST /previous

POST /next

\`\`\`

This keeps deterministic playback navigation independent from the natural-language parser.

**---**

**## Search intelligence**

The search system deliberately separates **\*\*understanding the request\*\*** from **\*\*finding the best YouTube result\*\***.

**### Intent layer**

The agent first tries deterministic parsing for obvious requests.

This avoids unnecessary LLM calls for commands such as:

\`\`\`text

next

previous

pause

resume

queue 3 phonk songs

play Blinding Lights by The Weeknd

play something similar

\`\`\`

Ambiguous requests can fall back to Ollama.

**### Discovery layer**

The discovery system builds useful search candidates and can perform parallel searches where appropriate.

**### Ranking layer**

The ranker scores candidates using multiple signals rather than simply taking the first YouTube result.

This matters because YouTube search can return:

\- lyrics videos

\- covers

\- live performances

\- tutorials

\- educational videos

\- compilations

\- playlists

\- reactions

\- unrelated videos containing the same words

The goal is not to ban every alternate version. Relevant variants can still win when they match the user's request.

**---**

**## Performance philosophy**

The application uses a **\*\*fast path + intelligent fallback\*\*** design.

**### Fast path**

Deterministic commands avoid Ollama where possible.

Benefits:

\- lower latency

\- fewer local LLM calls

\- predictable playback controls

\- faster common music requests

**### Intelligent fallback**

Ollama handles requests where interpretation requires more context.

The agent maintains conversational context so requests such as:

\`\`\`text

play Blinding Lights

play something similar

queue 5 more like this

\`\`\`

can be understood as a sequence rather than isolated searches.

**---**

**## Queue philosophy**

Queue handling is intentionally separated from "play this now".

For example:

\`\`\`text

queue 3 phonk songs

\`\`\`

adds tracks to the upcoming playback list.

Then:

\`\`\`text

next

previous

\`\`\`

navigate the player without requiring another YouTube search.

A user can also select a specific queued item through the queue UI/API.

Future improvements can extend this into a richer queue editor with:

\- drag-and-drop ordering

\- remove track

\- clear queue

\- play next

\- move to top

\- save queue

\- queue persistence

**---**

**## UI behavior**

The UI changes its visual presentation according to playback state.

**### Idle / paused**

The interface uses a darker monochrome appearance.

**### Playing**

The interface uses animated/colorful glass-style gradients.

The visual system is designed so the application can eventually react to playback characteristics such as:

\- beat intensity

\- bass

\- frequency bands

\- energy

\- tempo

A future audio-reactive visualizer can build on this foundation.

**---**

**## Project status**

This is an actively evolving personal/local project.

The current system already supports:

\- natural-language music control

\- YouTube search

\- intelligent result ranking

\- fuzzy song matching

\- similar-song discovery

\- music variants

\- podcast discovery

\- queue management

\- previous/next navigation

\- pause/resume

\- thumbnails

\- local web UI

\- Ollama integration

\- mpv playback

\- one-click Windows startup/shutdown

The architecture is deliberately modular so individual components can be improved without rewriting the entire application.

**---**

**## Known limitations / future work**

The project is functional, but there are several areas that can continue to improve.

**### Search intelligence**

\- Better understanding of ambiguous song titles

\- Better multilingual/transliteration handling

\- Better artist identification

\- Better YouTube channel verification

\- Better distinction between music videos and non-music content

\- More robust trending/current-information handling

**### Recommendations**

\- Better semantic similarity

\- More diverse recommendations

\- Genre/artist-aware recommendation scoring

\- Avoiding repeated recommendations across a session

**### Queue**

\- Drag-and-drop queue management

\- Remove/reorder individual tracks

\- Persistent queue storage

\- Better preloading

\- Background resolution of future queue items

**### Podcasts**

\- Better show/host recognition

\- Episode metadata

\- Duration-aware ranking

\- Podcast-specific history and recommendations

**### Audio-reactive UI**

\- real-time waveform

\- bass response

\- beat detection

\- frequency-reactive gradients

\- animated artwork

\- spectrum visualizer

**### Packaging**

A future release could bundle the local dependencies more cleanly and provide a proper Windows installer so that setup becomes:

\`\`\`text

Install → Launch → Listen

\`\`\`

instead of requiring any manual dependency configuration.

**---**

**## Security and privacy**

This project is designed primarily as a **\*\*local desktop application\*\***.

The default server binds to:

\`\`\`text

127.0.0.1

\`\`\`

which keeps the Flask interface local to the machine.

However:

\- Do not expose the Flask server publicly without adding authentication and appropriate security controls.

\- Do not commit API keys or secrets.

\- Do not commit \`.env\`.

\- Do not commit your Python virtual environment.

\- Be aware that YouTube/yt-dlp requests naturally access external YouTube services.

**---**

**## GitHub setup**

Before pushing the project, make sure the repository contains source/configuration templates rather than machine-specific runtime files.

Recommended repository contents:

\`\`\`text

local-music-agent/

├── agent/

├── tools/

├── templates/

├── app.py

├── config.py

├── launcher.py

├── check\_install.py

├── START\_LOCAL\_MUSIC\_AGENT.bat

├── START\_LOCAL\_MUSIC\_AGENT.vbs

├── STOP\_LOCAL\_MUSIC\_AGENT.vbs

├── close\_agent.bat

├── .env.example

├── .gitignore

├── requirements.txt

├── README.md

└── LICENSE

\`\`\`

Do **\*\*not\*\*** commit:

\`\`\`text

venv/

\_\_pycache\_\_/

\*.pyc

.env

.runtime.json

logs/

\*.log

.mpycache/

.mypy\_cache/

.pytest\_cache/

\`\`\`

Also do not commit locally installed copies of mpv or yt-dlp unless you intentionally want to redistribute them and have checked their licensing/distribution requirements.

**---**

**## First Git commit**

From the project root:

\`\`\`powershell

git init

git add .

git status

git commit -m "Initial release of Local Music Agent"

\`\`\`

Then create an empty repository on GitHub and connect it:

\`\`\`powershell

git branch -M main

git remote add origin https\://github.com/YOUR\_USERNAME/local-music-agent.git

git push -u origin main

\`\`\`

Replace:

\`\`\`text

YOUR\_USERNAME

\`\`\`

with your GitHub username.

Before the first push, **\*\*always run\*\***:

\`\`\`powershell

git status

\`\`\`

and verify that \`.env\`, \`venv\`, logs, caches, and other machine-specific files are not staged.

**---**

**## Development workflow**

The recommended workflow is:

\`\`\`text

Build

  ↓

Run locally

  ↓

Test natural-language commands

  ↓

Inspect logs / player behavior

  ↓

Fix one subsystem

  ↓

Retest

  ↓

Commit

  ↓

Push

\`\`\`

For larger changes, keep commits focused:

\`\`\`text

feat: improve YouTube ranking

fix: preserve queue during manual playback

fix: repair previous/next navigation

feat: add podcast discovery

feat: add audio reactive UI

perf: preload queued tracks

\`\`\`

This makes debugging and reverting changes significantly easier.

**---**

**## License**

Choose a license before publishing the repository.

For a permissive open-source project, the MIT License is a common option. Add the corresponding \`LICENSE\` file to the repository if you want others to reuse and modify the project.

**---**

**## Credits**

Built with:

\- Python

\- Flask

\- Ollama

\- mpv

\- yt-dlp

\- YouTube

\- HTML/CSS/JavaScript

The project combines these components into a local natural-language media agent rather than replacing any of them.

**---**

**## Roadmap**

The long-term goal is to turn Local Music Agent into a genuinely capable local media assistant:

\`\`\`text

Natural language

      ↓

Intent + context

      ↓

Music / podcast understanding

      ↓

YouTube discovery

      ↓

Intelligent ranking

      ↓

Preloaded queue

      ↓

mpv playback

      ↓

Audio-aware UI

\`\`\`

The next major milestones are:

\- smarter search intent

\- faster parallel queue resolution

\- reliable queue persistence

\- richer queue controls

\- stronger podcast intelligence

\- semantic recommendations

\- audio-reactive visuals

\- cleaner Windows packaging

\- optional persistent listening history

**---**

**## Contributing**

Issues, bug reports, experiments and improvements are welcome.

When reporting a search bug, include:

1\. The exact user command.

2\. The result the agent selected.

3\. The result you expected.

4\. Whether the request was music or podcast.

5\. Relevant console/log output if available.

For playback bugs, include:

1\. Current track.

2\. Queue contents.

3\. Command used (\`next\`, \`previous\`, etc.).

4\. What happened.

5\. What should have happened.

This makes search/ranking and playback issues much easier to reproduce.

**---**

**\*\*Local Music Agent — talk naturally, search intelligently, play locally.\*\***