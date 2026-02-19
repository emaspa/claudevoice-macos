# claudevoice (macOS)

Voice notifications for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Speaks aloud when Claude starts working, finishes a task, or needs your input — so you can step away from the screen and still know what's happening.

Supports two TTS engines: [edge-tts](https://pypi.org/project/edge-tts/) (Microsoft neural voices, free, no API key) and [ElevenLabs](https://elevenlabs.io/) (premium quality, requires API key). Uses macOS built-in `afplay` for playback.

Ported from [claudevoice](https://github.com/emaspa/claudevoice) (Windows).

## How it works

A single Python script (`notify.py`) hooks into three Claude Code events:

| Event | What you hear |
|---|---|
| **UserPromptSubmit** | A contextual acknowledgment based on your prompt |
| **Stop** | A summary of what was accomplished |
| **Notification** | Permission requests or idle prompts |

Messages are shaped by a **personality file** (`personality.md`) — a set of templated phrases the voice picks from randomly, giving it character and variety. The default personality is Jarvis from Iron Man.

Summaries are extracted from the session transcript. File paths, URLs, code blocks, and other non-speakable content are stripped so everything reads naturally as speech.

All hooks run asynchronously so they never block Claude.

### Direct invocation

Claude Code (or you) can also speak arbitrary messages at any time:

```bash
python3 notify.py --say "Deploying the latest changes now."
```

This is used by Claude during a session to narrate important actions — see `CLAUDE.md` for the guidelines.

## Setup

### 1. Install dependencies

```bash
pip install edge-tts elevenlabs
```

Only `edge-tts` is required. Install `elevenlabs` if you want to use their premium voices.

### 2. Clone the repo

```bash
git clone https://github.com/emaspa/claudevoice-macos.git
```

### 3. Configure Claude Code hooks

Add this to your `~/.claude/settings.json` (adjust the path to where you cloned the repo):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"/path/to/claudevoice-macos/notify.py\"",
            "async": true,
            "timeout": 15
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"/path/to/claudevoice-macos/notify.py\"",
            "async": true,
            "timeout": 30
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"/path/to/claudevoice-macos/notify.py\"",
            "async": true,
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

That's it. Start a new Claude Code session and you'll hear it.

### 4. Create your config

```bash
cp config.example.json config.json
```

Edit `config.json` with your preferences. This file is gitignored so your API keys stay local.

## Personality

Edit `personality.md` to change what the voice says and how it says it. The file has sections for each event type, with multiple template phrases the system picks from randomly:

```markdown
# Jarvis

## Acknowledgments
- Very well, sir. I'll see to that.
- Understood, sir. {prompt}

## Completions
- All sorted, sir. {summary}
- Task complete, sir. {summary}

## Permissions
- Sir, a moment of your attention. {message}

## Idle
- Standing by whenever you're ready, sir.
```

Placeholders (`{prompt}`, `{summary}`, `{message}`) are replaced with actual content. Templates without placeholders work as static phrases. If no personality file exists, the system falls back to `config.json` messages.

To create your own personality, copy the file and change the phrases. The `# Title` and description at the top are for your reference only.

## Configuration

Edit `config.json` to customize voice settings and fallback messages:

```json
{
    "enabled": true,
    "tts_engine": "edge-tts",
    "voice": "en-US-AndrewNeural",
    "rate": "+0%",
    "volume": "+0%",
    "pitch": "+0Hz",
    "elevenlabs": {
        "api_key": "",
        "voice_id": "JBFqnCBsd6RMkjVDRZzb",
        "model_id": "eleven_multilingual_v2",
        "output_format": "mp3_44100_128"
    },
    "debug": false,
    "messages": {
        "prompt_submit": "{prompt}",
        "prompt_submit_fallback": "On it.",
        "stop": "{summary}",
        "notification_permission_prompt": "Need your permission. {message}",
        "notification_idle_prompt": "Waiting for your input.",
        "notification_default": "{message}"
    }
}
```

### General
- **tts_engine** — `"edge-tts"` (default, free) or `"elevenlabs"` (premium quality)
- **enabled** — set to `false` to silence everything without removing the hooks
- **debug** — set to `true` to log raw hook event JSON to `debug.log`
- **messages** — fallback templates when personality.md is missing or a section is empty. `{prompt}`, `{summary}`, and `{message}` are replaced with actual content.

### edge-tts settings
- **voice** — any [edge-tts voice](https://gist.github.com/BettyJJ/17cbaa1de96235a7f5773b8571a4f422). Try `en-US-AriaNeural`, `en-GB-RyanNeural`, etc.
- **rate / volume / pitch** — adjust speech speed, loudness, and tone (e.g. `"+20%"`, `"-10%"`, `"+2Hz"`)

### ElevenLabs settings
To enable ElevenLabs, set `"tts_engine": "elevenlabs"` and provide your API key:

- **elevenlabs.api_key** — your ElevenLabs API key (or set the `ELEVENLABS_API_KEY` environment variable)
- **elevenlabs.voice_id** — voice to use. Browse voices at [elevenlabs.io/voices](https://elevenlabs.io/app/voice-library) or use the API to list them
- **elevenlabs.model_id** — TTS model. Options: `eleven_multilingual_v2` (default, best quality), `eleven_flash_v2_5` (lower latency, cheaper), `eleven_v3` (latest)
- **elevenlabs.output_format** — audio format. Default `mp3_44100_128` (best quality). Use `mp3_22050_64` for smaller files

## Requirements

- macOS (uses built-in `afplay` for audio playback)
- Python 3.9+
- Internet connection (both TTS engines call external services)
- ElevenLabs API key (only if using ElevenLabs engine)

## License

MIT
