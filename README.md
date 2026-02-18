# claudevoice (macOS)

Voice notifications for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Speaks aloud when Claude starts working, finishes a task, or needs your input — so you can step away from the screen and still know what's happening.

Uses [edge-tts](https://pypi.org/project/edge-tts/) (Microsoft neural voices, free, no API key) and macOS built-in `afplay` for playback.

Ported from [claudevoice](https://github.com/emaspa/claudevoice) (Windows).

## How it works

A single Python script (`notify.py`) hooks into three Claude Code events:

| Event | What you hear |
|---|---|
| **UserPromptSubmit** | *"On it."* |
| **Stop** | *"Done. {summary of what was completed}."* |
| **Notification** | *"Need your permission. {details}"* or *"Waiting for your input."* |

Summaries are extracted from the session transcript — the first sentence (what was done) and the last sentence (what you need to do next). Markdown, URLs, and code blocks are stripped so everything reads naturally as speech.

All hooks run asynchronously so they never block Claude.

## Setup

### 1. Install the dependency

```bash
pip install edge-tts
```

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

## Configuration

Edit `config.json` to customize:

```json
{
    "enabled": true,
    "voice": "en-US-GuyNeural",
    "rate": "+0%",
    "volume": "+0%",
    "pitch": "+0Hz",
    "debug": false,
    "messages": {
        "prompt_submit": "On it.",
        "stop": "Done. {summary}",
        "notification_permission_prompt": "Need your permission. {message}",
        "notification_idle_prompt": "Waiting for your input.",
        "notification_default": "{message}"
    }
}
```

- **voice** — any [edge-tts voice](https://gist.github.com/BettyJJ/17cbaa1de96235a7f5773b8571a4f422). Try `en-US-AriaNeural`, `en-GB-RyanNeural`, etc.
- **rate / volume / pitch** — adjust speech speed, loudness, and tone (e.g. `"+20%"`, `"-10%"`, `"+2Hz"`)
- **messages** — customize what's spoken for each event. `{summary}` and `{message}` are replaced with actual content.
- **debug** — set to `true` to log raw hook event JSON to `debug.log`
- **enabled** — set to `false` to silence everything without removing the hooks

## Requirements

- macOS (uses built-in `afplay` for audio playback)
- Python 3.9+
- Internet connection (edge-tts calls Microsoft's TTS service)

## License

MIT
