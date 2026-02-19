"""Claude Code voice notification hook (macOS).

Speaks aloud when Claude starts, finishes, or needs user input.
Supports personality-driven message templates and direct CLI invocation.
Uses edge-tts (Microsoft neural voices) for TTS and afplay for playback.
"""

import asyncio
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

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


# --- Personality ---

# Maps personality.md section headers to config.json message keys
_SECTION_MAP = {
    "acknowledgments": "prompt_submit",
    "completions": "stop",
    "permissions": "notification_permission_prompt",
    "idle": "notification_idle_prompt",
}


def _load_personality() -> dict[str, list[str]]:
    """Parse personality.md into {message_key: [template, ...]}."""
    personality_path = SCRIPT_DIR / "personality.md"
    try:
        text = personality_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}

    sections: dict[str, list[str]] = {}
    current_key = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            header = line[3:].strip().lower()
            current_key = _SECTION_MAP.get(header)
        elif current_key and line.startswith("- "):
            template = line[2:].strip()
            if template:
                sections.setdefault(current_key, []).append(template)
    return sections


def _pick_template(personality: dict[str, list[str]], key: str) -> str | None:
    """Pick a random template from the personality for the given key."""
    templates = personality.get(key)
    if templates:
        return random.choice(templates)
    return None


# --- Message resolution ---


def _split_sentences(text: str) -> list[str]:
    """Split text into complete sentences."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in parts if s.strip()]


def _take_sentences(text: str, max_sentences: int = 3) -> str:
    """Keep up to max_sentences complete sentences from text.

    Avoids cutting mid-thought. If the text has no sentence boundaries,
    returns it as-is (better to say a full thought than chop it).
    """
    sentences = _split_sentences(text)
    if not sentences:
        return text.strip()
    kept = sentences[:max_sentences]
    return " ".join(kept)


def _strip_paths(text: str) -> str:
    """Remove file paths that add nothing as speech."""
    # Unix absolute paths: /foo/bar (but not standalone /)
    text = re.sub(r"(?<!\w)/[\w.\-/]+", "", text)
    # Dotted relative paths: ./foo, ../foo
    text = re.sub(r"\.{1,2}/[\w.\-/]+", "", text)
    # Clean up orphaned prepositions left after path removal
    text = re.sub(r"\s+(?:in|at|from|to|of|on)\s*$", "", text, flags=re.IGNORECASE)
    return text


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
    # Remove file paths
    line = _strip_paths(line)
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
    """Extract the first complete sentence from text."""
    sentences = _split_sentences(text)
    if sentences:
        return sentences[0]
    return text.strip()


def _clean_prompt(prompt: str) -> str:
    """Extract the speakable intent from a user prompt.

    Takes the first meaningful sentence — enough to capture what was asked
    without reading back the entire prompt verbatim.
    """
    lines = _get_speakable_lines(prompt)
    if not lines:
        return ""
    return _first_sentence(lines[0])


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

        # Gather all speakable text, take the most meaningful sentences
        full_text = " ".join(lines)
        return _take_sentences(full_text, max_sentences=2)

    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return ""


def resolve_message(
    event: dict, config: dict, personality: dict[str, list[str]]
) -> str | None:
    hook_event = event.get("hook_event_name", "")
    messages = config.get("messages", DEFAULT_CONFIG["messages"])

    if hook_event == "UserPromptSubmit":
        prompt = _clean_prompt(event.get("prompt", ""))
        template = _pick_template(personality, "prompt_submit")
        if template:
            # If the template uses {prompt} but we have nothing speakable,
            # pick a template without {prompt} or fall back to config
            if "{prompt}" in template and not prompt:
                no_placeholder = [
                    t for t in personality.get("prompt_submit", [])
                    if "{prompt}" not in t
                ]
                if no_placeholder:
                    return random.choice(no_placeholder)
                return messages.get("prompt_submit", "On it.")
            return _take_sentences(template.replace("{prompt}", prompt))
        # No personality — use config template
        fallback = messages.get("prompt_submit", "{prompt}")
        if "{prompt}" in fallback:
            if not prompt:
                return messages.get("prompt_submit_fallback", "On it.")
            return _take_sentences(fallback.replace("{prompt}", prompt))
        return fallback

    if hook_event == "Stop":
        if event.get("stop_hook_active", False):
            return None
        summary = event.get("transcript_summary", "")
        if not summary:
            transcript_path = event.get("transcript_path", "")
            if transcript_path:
                summary = _extract_summary(transcript_path)
        template = _pick_template(personality, "stop")
        if template:
            if not summary:
                # Strip the {summary} placeholder and any trailing space
                text = template.replace("{summary}", "").strip()
            else:
                text = template.replace("{summary}", summary)
            return _take_sentences(text)
        # No personality — use config template
        template = messages.get("stop", "{summary}")
        if not summary:
            text = template.replace("{summary}", "").strip()
        else:
            prefix = template.split("{summary}")[0].strip().rstrip(".").lower()
            if prefix and summary.lower().startswith(prefix):
                text = summary
            else:
                text = template.replace("{summary}", summary)
        return _take_sentences(text)

    if hook_event == "Notification":
        notif_type = event.get("notification_type", "")
        key = f"notification_{notif_type}"
        # Try personality first
        template = _pick_template(personality, key)
        if not template and notif_type == "idle_prompt":
            template = _pick_template(personality, "notification_idle_prompt")
        if template:
            raw_message = event.get("message", "")
            text = template.replace("{message}", raw_message)
            return _take_sentences(text)
        # Fall back to config
        template = messages.get(key, messages.get("notification_default", "{message}"))
        raw_message = event.get("message", "Notification")
        text = template.replace("{message}", raw_message)
        return _take_sentences(text)

    return None


# --- TTS ---


def _speak_elevenlabs(text: str, config: dict) -> None:
    from elevenlabs import save
    from elevenlabs.client import ElevenLabs

    el_config = config.get("elevenlabs", {})
    api_key = el_config.get("api_key") or os.environ.get("ELEVENLABS_API_KEY", "")
    client = ElevenLabs(api_key=api_key)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=el_config.get("voice_id", "JBFqnCBsd6RMkjVDRZzb"),
            model_id=el_config.get("model_id", "eleven_multilingual_v2"),
            output_format=el_config.get("output_format", "mp3_44100_128"),
        )
        save(audio, tmp_path)
        play_mp3(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def _generate_edge_tts(text: str, config: dict, tmp_path: str) -> None:
    import edge_tts

    comm = edge_tts.Communicate(
        text,
        voice=config.get("voice", "en-US-GuyNeural"),
        rate=config.get("rate", "+0%"),
        volume=config.get("volume", "+0%"),
        pitch=config.get("pitch", "+0Hz"),
    )
    await comm.save(tmp_path)


def _speak_edge_tts(text: str, config: dict) -> None:
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        asyncio.run(_generate_edge_tts(text, config, tmp_path))
        play_mp3(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def speak(text: str, config: dict) -> None:
    tts_engine = config.get("tts_engine", "edge-tts")
    if tts_engine == "elevenlabs":
        _speak_elevenlabs(text, config)
    else:
        _speak_edge_tts(text, config)


# --- Entry point ---


def _debug_log(event: dict) -> None:
    log_path = SCRIPT_DIR / "debug.log"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, indent=2, default=str) + "\n---\n")
    except OSError:
        pass


def main() -> None:
    config = load_config()

    if not config.get("enabled", True):
        return

    # CLI mode: python3 notify.py --say "message"
    if len(sys.argv) > 1 and sys.argv[1] == "--say":
        message = " ".join(sys.argv[2:]).strip()
        if message:
            speak(message, config)
        return

    # Hook mode: read event from stdin
    raw = sys.stdin.read()
    event = json.loads(raw) if raw.strip() else {}

    if config.get("debug", False):
        _debug_log(event)

    personality = _load_personality()
    message = resolve_message(event, config, personality)
    if message:
        speak(message, config)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"claudevoice error: {e}", file=sys.stderr)
        sys.exit(0)
