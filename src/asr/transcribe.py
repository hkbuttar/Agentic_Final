"""Fragment-based ASR: record/upload a WAV/MP3 -> transcript. Whisper via
faster-whisper for lower CPU latency, per the top-level README's ASR spec.
Language is auto-detected (not forced), which is what gives basic
multilingual/accent handling — Whisper's own language ID, not a separate
step.
"""
from dataclasses import dataclass
from typing import Optional

from faster_whisper import WhisperModel

from config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL_SIZE


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    text: str
    language: str
    language_probability: float
    segments: list[TranscriptSegment]


_model: Optional[WhisperModel] = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
        )
    return _model


def transcribe(audio_path: str) -> Transcript:
    segments_iter, info = _get_model().transcribe(audio_path, beam_size=5)
    segments = [
        TranscriptSegment(start=s.start, end=s.end, text=s.text.strip()) for s in segments_iter
    ]
    text = " ".join(s.text for s in segments).strip()
    return Transcript(
        text=text,
        language=info.language,
        language_probability=info.language_probability,
        segments=segments,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python transcribe.py <audio_path>", file=sys.stderr)
        raise SystemExit(1)

    result = transcribe(sys.argv[1])
    print(f"[{result.language} p={result.language_probability:.2f}] {result.text}")
    for seg in result.segments:
        print(f"  {seg.start:6.2f}-{seg.end:6.2f}  {seg.text}")
