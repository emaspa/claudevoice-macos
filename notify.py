"""Claude Code voice notification hook (macOS).

Speaks aloud when Claude finishes a task or needs user input.
Uses edge-tts (Microsoft neural voices) for TTS and afplay for playback.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MAX_MESSAGE_LENGTH = 250

# --- Audio playback (macOS) ---


def play_mp3(path: str) -> None:
    """Play an MP3 file using macOS built-in afplay."""
    subprocess.run(
        ["/usr/bin/afplay", path],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# --- Config ---

DEFAULT_CONFIG = {
    "enabled": True,
    "voice": "en-US-GuyNeural",
    "rate": "+0%",
    "volume": "+0%",
    "pitch": "+0Hz",
    "messages": {
        "prompt_submit": "On it.",
        "stop": "Done. {summary}",
        "notification_permission_prompt": "Need your permission. {message}",
        "notification_idle_prompt": "Waiting for your input.",
        "notification_default": "{message}",
    },
}


def load_config() -> dict:
    config_path = SCRIPT_DIR / "config.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Config error, using defaults: {e}", file=sys.stderr)
        return DEFAULT_CONFIG


# --- Message resolution ---


def _truncate(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    # Cut at last sentence boundary within limit, or just truncate
    cut = text[:max_len]
    last_period = cut.rfind(".")
    if last_period > max_len // 2:
        return cut[: last_period + 1]
    return cut.rstrip() + "."


def _clean_line(line: str) -> str:
    """Strip markdown and non-speakable content from a single line."""
    # Remove inline code backticks but keep content
    line = re.sub(r"`([^`]+)`", r"\1", line)
    # Remove URLs
    line = re.sub(r"https?://\S+", "", line)
    # Remove markdown links, keep the label
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
    # Remove bold/italic markers
    line = re.sub(r"\*{1,2}", "", line)
    # Remove headers, bullets, blockquotes at start of line
    line = re.sub(r"^[#>\-*\s]+", "", line)
    # Collapse whitespace
    line = re.sub(r"\s+", " ", line).strip()
    return line


def _get_speakable_lines(text: str) -> list[str]:
    """Get non-empty, cleaned lines that are worth speaking."""
    # Remove code blocks first (they span multiple lines)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Split, clean each line, keep meaningful ones
    result = []
    for line in text.splitlines():
        cleaned = _clean_line(line)
        if len(cleaned) > 5:
            result.append(cleaned)
    return result


def _first_sentence(text: str) -> str:
    """Extract the first sentence from text."""
    # Match up to the first sentence-ending punctuation
    m = re.match(r"(.+?[.!?])\s", text + " ")
    if m and len(m.group(1)) < 150:
        return m.group(1)
    return text[:150]


def _extract_summary(transcript_path: str) -> str:
    """Build a summary from the last assistant message in the transcript.

    Strategy: take the first meaningful sentence (what was done) and the
    last meaningful sentence (what the user needs to do), if different.
    """
    try:
        last_text = ""
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("type") == "assistant":
                    message = entry.get("message", {})
                    for block in message.get("content", []):
                        if block.get("type") == "text":
                            last_text = block["text"]
        if not last_text:
            return ""

        lines = _get_speakable_lines(last_text)
        if not lines:
            return ""

        first = _first_sentence(lines[0])
        last = _first_sentence(lines[-1])

        # If first and last are the same (short response), just use one
        if first == last or len(lines) == 1:
            return first

        # Combine: what was done + what's needed from the user
        return f"{first} {last}"

    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return ""


def resolve_message(event: dict, config: dict) -> str | None:
    hook_event = event.get("hook_event_name", "")
    messages = config.get("messages", DEFAULT_CONFIG["messages"])

    if hook_event == "UserPromptSubmit":
        return messages.get("prompt_submit", "On it.")

    if hook_event == "Stop":
        if event.get("stop_hook_active", False):
            return None
        template = messages.get("stop", "Done. {summary}")
        summary = event.get("transcript_summary", "")
        if not summary:
            transcript_path = event.get("transcript_path", "")
            if transcript_path:
                summary = _extract_summary(transcript_path)
        if not summary:
            text = template.replace("{summary}", "").strip()
        else:
            # Avoid stuttering like "Done. Done. ..." when the summary
            # already starts with the same prefix as the template.
            prefix = template.split("{summary}")[0].strip().rstrip(".").lower()
            if prefix and summary.lower().startswith(prefix):
                text = summary
            else:
                text = template.replace("{summary}", summary)
        return _truncate(text)

    if hook_event == "Notification":
        notif_type = event.get("notification_type", "")
        key = f"notification_{notif_type}"
        template = messages.get(key, messages.get("notification_default", "{message}"))
        raw_message = event.get("message", "Notification")
        text = template.replace("{message}", raw_message)
        return _truncate(text)

    return None


# --- TTS ---


async def _generate_and_play(text: str, config: dict) -> None:
    import edge_tts

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        comm = edge_tts.Communicate(
            text,
            voice=config.get("voice", "en-US-GuyNeural"),
            rate=config.get("rate", "+0%"),
            volume=config.get("volume", "+0%"),
            pitch=config.get("pitch", "+0Hz"),
        )
        await comm.save(tmp_path)
        play_mp3(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def speak(text: str, config: dict) -> None:
    asyncio.run(_generate_and_play(text, config))


# --- Entry point ---


def _debug_log(event: dict) -> None:
    log_path = SCRIPT_DIR / "debug.log"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, indent=2, default=str) + "\n---\n")
    except OSError:
        pass


def main() -> None:
    raw = sys.stdin.read()
    event = json.loads(raw) if raw.strip() else {}

    config = load_config()

    if config.get("debug", False):
        _debug_log(event)

    if not config.get("enabled", True):
        return

    message = resolve_message(event, config)
    if message:
        speak(message, config)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"claudevoice error: {e}", file=sys.stderr)
        sys.exit(0)
