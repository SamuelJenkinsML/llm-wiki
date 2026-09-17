#!/usr/bin/env python3
"""Jarvis TTS engine — ElevenLabs streaming speech via aplay.

Usage:
    tts.py --text "Good evening, sir."     # speak literal text
    tts.py --from-stdin                     # hook mode: read hook JSON from stdin
    tts.py --daily                          # read today's daily briefing highlights
    tts.py --file PATH                      # read and speak a file
    tts.py --greet                          # speak a greeting
"""

import argparse
import json
import os
import signal
import subprocess
import sys
from datetime import date
from pathlib import Path

from voice.config import (
    TTS_PID_FILE,
    TTS_LOG_FILE,
    get_api_key,
    is_voice_enabled,
    load_config,
)
from voice.text_filter import (
    extract_briefing_highlights,
    filter_for_speech,
)


def log(msg: str) -> None:
    """Append to TTS log file."""
    try:
        with open(TTS_LOG_FILE, "a") as f:
            f.write(f"{msg}\n")
    except OSError:
        pass


def kill_prior_playback() -> None:
    """Kill any running aplay from a previous TTS invocation."""
    try:
        if TTS_PID_FILE.exists():
            pid = int(TTS_PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
    except (ValueError, ProcessLookupError, OSError):
        pass


def speak(text: str, config=None) -> None:
    """Stream text through ElevenLabs and play via aplay."""
    if not text or not text.strip():
        return

    api_key = get_api_key()
    if not api_key:
        log("ELEVENLABS_API_KEY not set, skipping TTS")
        return

    if config is None:
        config = load_config()

    voice_id = config.tts.voice_id
    if not voice_id:
        log("No voice_id configured, skipping TTS")
        return

    kill_prior_playback()

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=api_key)
        audio_stream = client.text_to_speech.stream(
            voice_id=voice_id,
            text=text,
            model_id=config.tts.model_id,
            output_format="pcm_16000",
        )

        # Pipe streaming PCM to aplay (routes through PipeWire ALSA layer)
        proc = subprocess.Popen(
            ["aplay", "-f", "S16_LE", "-r", "16000", "-c", "1", "-q"],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        # Record PID so it can be killed
        TTS_PID_FILE.write_text(str(proc.pid))

        for chunk in audio_stream:
            try:
                proc.stdin.write(chunk)
            except BrokenPipeError:
                break  # aplay was killed (user pressed stop)

        proc.stdin.close()
        proc.wait()

    except Exception as e:
        log(f"TTS error: {e}")
    finally:
        try:
            TTS_PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def extract_last_assistant_text(hook_json: str) -> str:
    """Extract the last assistant message text from a Stop hook payload.

    The Stop hook JSON contains a transcript_path pointing to a JSONL file.
    We read the last assistant message from that transcript.
    """
    try:
        payload = json.loads(hook_json)
    except json.JSONDecodeError:
        log("Failed to parse hook JSON")
        return ""

    transcript_path = payload.get("transcript_path", "")
    if not transcript_path or not Path(transcript_path).exists():
        log(f"Transcript not found: {transcript_path}")
        return ""

    # Read the JSONL transcript and find the last assistant message
    last_assistant_text = ""
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("role") == "assistant":
                    content = entry.get("content", [])
                    if isinstance(content, str):
                        last_assistant_text = content
                    elif isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                        if text_parts:
                            last_assistant_text = "\n".join(text_parts)
    except OSError as e:
        log(f"Error reading transcript: {e}")
        return ""

    return last_assistant_text


def get_daily_briefing_text(config) -> str:
    """Read today's daily briefing and extract highlights."""
    vault_path = Path(config.daily.vault_path).expanduser()
    today = date.today().isoformat()
    briefing_path = vault_path / "_llm" / "daily" / f"{today}.md"

    if not briefing_path.exists():
        return "No briefing found for today, sir."

    text = briefing_path.read_text()
    highlights = extract_briefing_highlights(text)

    if not highlights:
        return "Today's briefing appears to be empty, sir."

    return f"Good morning, sir. Here's your briefing. {highlights}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis TTS engine")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Speak literal text")
    group.add_argument("--from-stdin", action="store_true",
                       help="Hook mode: read hook JSON from stdin")
    group.add_argument("--daily", action="store_true",
                       help="Read today's daily briefing highlights")
    group.add_argument("--file", help="Read and speak a file")
    group.add_argument("--greet", action="store_true",
                       help="Speak a greeting")
    args = parser.parse_args()

    if not is_voice_enabled():
        sys.exit(0)

    config = load_config()

    if not config.tts.enabled:
        sys.exit(0)

    if args.text:
        speak(args.text, config)

    elif args.from_stdin:
        hook_json = sys.stdin.read()
        text = extract_last_assistant_text(hook_json)
        if text:
            filtered = filter_for_speech(
                text,
                mode=config.tts.mode,
                threshold=config.tts.smart_threshold_words,
                truncate_sentences=config.tts.truncate_sentences,
            )
            speak(filtered, config)

    elif args.daily:
        text = get_daily_briefing_text(config)
        speak(text, config)

    elif args.file:
        path = Path(args.file)
        if not path.exists():
            log(f"File not found: {args.file}")
            sys.exit(0)
        text = path.read_text()
        filtered = filter_for_speech(
            text,
            mode=config.tts.mode,
            threshold=config.tts.smart_threshold_words,
            truncate_sentences=config.tts.truncate_sentences,
        )
        speak(filtered, config)

    elif args.greet:
        speak("Good evening, sir. All systems are online.", config)


if __name__ == "__main__":
    main()
