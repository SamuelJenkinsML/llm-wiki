#!/usr/bin/env python3
"""Jarvis STT engine — mic listener with VAD and faster-whisper transcription.

Runs as a long-lived process in a tmux pane. Listens to the microphone,
detects speech via Silero VAD, transcribes with faster-whisper, and injects
the text into the Claude Code tmux pane via tmux send-keys.

Usage:
    stt.py              # start listening (continuous VAD mode)
    stt.py --test       # record 3 seconds, print transcription, exit
    stt.py --auto-send  # also press Enter after injecting text
"""

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from voice.config import STT_PID_FILE, load_config

# Globals for signal handling
_paused = False
_running = True


def status(msg: str) -> None:
    """Print a status line, overwriting the previous one."""
    print(f"\r\033[K{msg}", end="", flush=True)


def status_line(msg: str) -> None:
    """Print a status line on its own line."""
    print(f"\r\033[K{msg}", flush=True)


def check_tmux_target(target: str) -> bool:
    """Verify the tmux target pane exists."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", target.split(".")[0].split(":")[0]],
        capture_output=True,
    )
    return result.returncode == 0


def inject_text(text: str, target: str, auto_send: bool = False) -> None:
    """Send transcribed text to the Claude Code tmux pane."""
    # Use send-keys to type the text into the target pane
    subprocess.run(
        ["tmux", "send-keys", "-t", target, "-l", text],
        check=True,
        capture_output=True,
    )
    if auto_send:
        subprocess.run(
            ["tmux", "send-keys", "-t", target, "Enter"],
            check=True,
            capture_output=True,
        )


def load_whisper_model(model_name: str, compute_type: str):
    """Load the faster-whisper model."""
    from faster_whisper import WhisperModel

    status("Loading whisper model (first run downloads ~150MB)...")
    model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
    return model


def load_vad_model():
    """Load Silero VAD model."""
    import torch

    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        onnx=True,
    )
    return model, utils


def transcribe(model, audio: np.ndarray) -> str:
    """Transcribe audio array with faster-whisper."""
    # faster-whisper expects float32 audio normalized to [-1, 1]
    audio_float = audio.astype(np.float32)
    if audio_float.max() > 1.0:
        audio_float = audio_float / 32768.0

    segments, _ = model.transcribe(audio_float, beam_size=5)
    text = " ".join(seg.text for seg in segments).strip()
    return text


def run_test_mode(config) -> None:
    """Record 3 seconds and print transcription."""
    print("Recording 3 seconds of audio...")
    sample_rate = 16000
    audio = sd.rec(
        int(3 * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    audio = audio.flatten()

    model = load_whisper_model(config.stt.model, config.stt.compute_type)
    text = transcribe(model, audio)
    print(f"\nTranscription: {text}")


def handle_sigusr1(signum, frame):
    """Toggle pause state on SIGUSR1."""
    global _paused
    _paused = not _paused
    if _paused:
        status_line("🔇 Mic paused")
    else:
        status_line("🎙  Listening...")


def handle_sigterm(signum, frame):
    """Clean shutdown on SIGTERM."""
    global _running
    _running = False


def run_listener(config, auto_send: bool = False) -> None:
    """Main listening loop with VAD-based speech detection."""
    global _paused, _running

    target = config.stt.tmux_target
    silence_ms = config.stt.silence_ms
    sample_rate = 16000
    chunk_duration_ms = 30  # VAD processes 30ms chunks
    chunk_samples = int(sample_rate * chunk_duration_ms / 1000)

    # Verify tmux target
    if not check_tmux_target(target):
        print(f"Error: tmux target '{target}' not found.")
        print("Start Claude Code in tmux first:")
        print("  tmux new -s jarvis")
        print("  claude")
        sys.exit(1)

    # Write PID file
    STT_PID_FILE.write_text(str(os.getpid()))

    # Set up signal handlers
    signal.signal(signal.SIGUSR1, handle_sigusr1)
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Load models
    whisper_model = load_whisper_model(config.stt.model, config.stt.compute_type)
    status_line("Whisper model loaded.")

    vad_model, vad_utils = load_vad_model()
    (get_speech_timestamps, _, _, _, _) = vad_utils
    status_line("VAD model loaded.")

    status_line("🎙  Listening...")
    voice_state = "on" if not Path("/tmp/jarvis-voice-off").exists() else "off"

    # Audio buffer for current utterance
    audio_buffer = []
    is_speaking = False
    silence_chunks = 0
    silence_threshold = int(silence_ms / chunk_duration_ms)

    def audio_callback(indata, frames, time_info, callback_status):
        nonlocal audio_buffer, is_speaking, silence_chunks

        if _paused or not _running:
            return

        chunk = indata[:, 0].copy()

        # Run VAD on the chunk
        import torch
        tensor = torch.from_numpy(chunk).float()
        speech_prob = vad_model(tensor, sample_rate).item()

        if speech_prob > 0.5:
            # Speech detected
            if not is_speaking:
                is_speaking = True
                audio_buffer = []  # start fresh
                status("💬 Speech detected...")
            audio_buffer.append(chunk)
            silence_chunks = 0
        elif is_speaking:
            # Still recording but silence
            audio_buffer.append(chunk)
            silence_chunks += 1

            if silence_chunks >= silence_threshold:
                # End of utterance — trigger transcription
                is_speaking = False
                silence_chunks = 0
                audio_data = np.concatenate(audio_buffer)
                audio_buffer = []

                # Transcribe in a thread to avoid blocking audio
                threading.Thread(
                    target=_process_utterance,
                    args=(audio_data, whisper_model, target, auto_send),
                    daemon=True,
                ).start()

    def _process_utterance(audio_data, model, target, auto_send):
        status("🔄 Transcribing...")
        text = transcribe(model, audio_data)
        if text:
            try:
                inject_text(text, target, auto_send)
                status_line(f"📤 Sent: \"{text}\"")
            except subprocess.CalledProcessError:
                status_line(f"⚠  Failed to send to tmux: \"{text}\"")
        else:
            status_line("🎙  (no speech detected)")
        time.sleep(0.5)
        if not _paused:
            status("🎙  Listening...")

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=chunk_samples,
            callback=audio_callback,
        ):
            while _running:
                time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    except sd.PortAudioError as e:
        print(f"\nError: No audio input device found. {e}")
        print("Check available devices with: python -m sounddevice")
        sys.exit(1)
    finally:
        STT_PID_FILE.unlink(missing_ok=True)
        print("\n🛑 STT stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis STT engine")
    parser.add_argument("--test", action="store_true",
                        help="Record 3 seconds and print transcription")
    parser.add_argument("--auto-send", action="store_true",
                        help="Auto-press Enter after injecting text")
    args = parser.parse_args()

    config = load_config()

    if args.test:
        run_test_mode(config)
    else:
        run_listener(config, auto_send=args.auto_send)


if __name__ == "__main__":
    main()
