"""Stage 5: generate an accurately-timed .srt caption file from the finished
narration audio, using local Whisper transcription (no API cost)."""
from pathlib import Path

from .utils import DRY_RUN, log


def _format_timestamp(seconds: float) -> str:
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_captions(audio_path: Path, scenes: list, run_dir: Path) -> Path:
    srt_path = run_dir / "captions.srt"

    if DRY_RUN:
        log("Generating captions (mock, derived from scene durations)")
        lines = []
        t = 0.0
        for i, scene in enumerate(scenes, start=1):
            start, end = t, t + scene["duration"]
            lines.append(
                f"{i}\n{_format_timestamp(start)} --> {_format_timestamp(end)}\n"
                f"{scene['narration']}\n"
            )
            t = end
        srt_path.write_text("\n".join(lines), encoding="utf-8")
        return srt_path

    log("Transcribing narration with Whisper for accurately-timed captions")
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), word_timestamps=False)

    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(
            f"{i}\n{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}\n"
            f"{seg.text.strip()}\n"
        )
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    return srt_path
