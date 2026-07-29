"""TTS: text -> speech via Azure Speech, per the top-level README's TTS
spec. Synthesizes to a WAV file rather than the default speaker — callers
(CLI, future backend API) decide how/whether to play it back.
"""
import azure.cognitiveservices.speech as speechsdk

from config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, AZURE_SPEECH_VOICE


class TTSError(RuntimeError):
    pass


def synthesize(text: str, out_path: str) -> str:
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        raise TTSError("AZURE_SPEECH_KEY / AZURE_SPEECH_REGION are not set")

    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = AZURE_SPEECH_VOICE
    audio_config = speechsdk.audio.AudioOutputConfig(filename=out_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    result = synthesizer.speak_text_async(text).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = result.cancellation_details
        reason = details.error_details if details else result.reason
        raise TTSError(f"speech synthesis failed: {reason}")
    return out_path


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or "Hello, this is a test of the text to speech pipeline."
    path = synthesize(text, "tts_output.wav")
    print(f"wrote {path}")
