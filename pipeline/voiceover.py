"""Stage 3: synthesize narration to speech, one clip per scene (so each scene's
exact spoken duration is known for timing the visuals)."""
import subprocess
import wave
from pathlib import Path

from .utils import ASSETS_DIR, DRY_RUN, load_channel_config, log


def _silent_wav(path: Path, seconds: float = 3.0, rate: int = 24000) -> None:
    """Used only in dry-run / no-credentials mode so the rest of the pipeline
    still has real audio files with real (fake) durations to work with."""
    n_frames = int(seconds * rate)
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"\x00\x00" * n_frames)


def _synthesize_google(text: str, out_path: Path, voice_name: str, speaking_rate: float) -> None:
    from google.cloud import texttospeech

    client = texttospeech.TextToSpeechClient()
    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="-".join(voice_name.split("-")[:2]), name=voice_name
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        speaking_rate=speaking_rate,
    )
    response = client.synthesize_speech(
        input=input_text, voice=voice, audio_config=audio_config
    )
    with open(out_path, "wb") as f:
        f.write(response.audio_content)


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "r") as f:
        return f.getnframes() / f.getframerate()


def synthesize_scenes(scenes: list, run_dir: Path) -> list:
    """Mutates scenes in place, adding 'audio_path' and 'duration' to each,
    and returns the list."""
    config = load_channel_config()
    tts_cfg = config["tts"]
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(scenes):
        out_path = audio_dir / f"scene_{i:03d}.wav"
        if DRY_RUN:
            log(f"Synthesizing scene {i} (mock, silent placeholder)")
            _silent_wav(out_path)
        else:
            log(f"Synthesizing scene {i}")
            _synthesize_google(
                scene["narration"],
                out_path,
                tts_cfg["voice_name"],
                tts_cfg.get("speaking_rate", 1.0),
            )
        scene["audio_path"] = str(out_path)
        scene["duration"] = _wav_duration(out_path)

    return scenes


def concat_audio(scenes: list, run_dir: Path) -> Path:
    """Concatenates all scene audio clips into one full narration track."""
    list_path = run_dir / "audio" / "concat_list.txt"
    with open(list_path, "w") as f:
        for scene in scenes:
            f.write(f"file '{Path(scene['audio_path']).resolve()}'\n")

    out_path = run_dir / "audio" / "full_narration.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path), "-c", "copy", str(out_path),
        ],
        check=True, capture_output=True,
    )
    return out_path
