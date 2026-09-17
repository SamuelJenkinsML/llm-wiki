"""Jarvis voice configuration loader."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path("~/.config/jarvis/voice.toml").expanduser()
CREDENTIALS_PATH = Path("~/.config/jarvis/credentials.env").expanduser()
VOICE_OFF_SENTINEL = Path("/tmp/jarvis-voice-off")
TTS_PID_FILE = Path("/tmp/jarvis-tts.pid")
STT_PID_FILE = Path("/tmp/jarvis-stt.pid")
TTS_LOG_FILE = Path("/tmp/jarvis-tts.log")


@dataclass
class TTSConfig:
    enabled: bool = True
    voice_id: str = ""
    model_id: str = "eleven_turbo_v2_5"
    mode: str = "smart"  # full | truncate | smart
    truncate_sentences: int = 3
    smart_threshold_words: int = 200


@dataclass
class STTConfig:
    enabled: bool = True
    model: str = "base.en"
    compute_type: str = "int8"
    silence_ms: int = 800
    tmux_target: str = "jarvis:0.0"
    auto_send: bool = False


@dataclass
class DailyConfig:
    vault_path: str = "~/Documents/Day to day"
    sections: list[str] = field(default_factory=lambda: [
        "Today at a Glance",
        "Today's Focus",
        "Health & Training",
        "Backlog Pick of the Day",
    ])


@dataclass
class VoiceConfig:
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    daily: DailyConfig = field(default_factory=DailyConfig)


def load_config() -> VoiceConfig:
    """Load voice config from TOML file, falling back to defaults."""
    config = VoiceConfig()

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)

        if "tts" in data:
            for k, v in data["tts"].items():
                if hasattr(config.tts, k):
                    setattr(config.tts, k, v)

        if "stt" in data:
            for k, v in data["stt"].items():
                if hasattr(config.stt, k):
                    setattr(config.stt, k, v)

        if "daily" in data:
            for k, v in data["daily"].items():
                if hasattr(config.daily, k):
                    setattr(config.daily, k, v)

    # Environment variables override config file
    if api_key := os.environ.get("ELEVENLABS_API_KEY"):
        pass  # stored in env, accessed directly by tts.py
    if voice_id := os.environ.get("ELEVENLABS_VOICE_ID"):
        config.tts.voice_id = voice_id

    return config


def get_api_key() -> str | None:
    """Get ElevenLabs API key from environment."""
    return os.environ.get("ELEVENLABS_API_KEY")


def is_voice_enabled() -> bool:
    """Check if voice output is currently enabled (not toggled off)."""
    return not VOICE_OFF_SENTINEL.exists()
