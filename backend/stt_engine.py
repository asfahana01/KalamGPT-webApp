"""
stt_engine.py
Speech-to-Text engine for KalamGPT's Input Processing Layer.

Uses faster-whisper (a CTranslate2 reimplementation of OpenAI Whisper) for
fast, accurate, fully local transcription — no paid API, no internet
dependency at inference time.

Requirements (add to requirements.txt):
    faster-whisper==1.0.3

No system-level ffmpeg.exe is required. faster-whisper decodes audio
internally via the `av` package (PyAV), which ships its own compiled
codec libraries inside the pip wheel — it is not a standalone executable,
so it won't trip Application Control / AppLocker policies the way a
separate ffmpeg.exe process can on locked-down (e.g. college lab) machines.
`av` installs automatically as a dependency of faster-whisper.
"""

import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class STTEngine:
    """
    Wraps faster-whisper to transcribe an uploaded audio file (webm, mp3,
    ogg, wav, m4a, etc.) into text. Mirrors the loading pattern of your
    existing MultimodalEngine (BLIP) class — load once, reuse everywhere.
    """

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        """
        model_size: tiny | base | small | medium | large-v3
                    'base' is a good accuracy/speed tradeoff for a CPU-only
                    Flask server. Use 'small' if latency isn't critical.
        device: 'cpu' for local dev; 'cuda' if you deploy with a GPU later.
        compute_type: 'int8' keeps CPU memory low; use 'float16' on GPU.
        """
        logger.info(f"Loading Whisper STT model: {model_size} ({device}/{compute_type})")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, file_path: str, language: str = None) -> dict:
        """
        Transcribes an audio file to text.

        Args:
            file_path: path to the uploaded audio file (any common format)
            language: optional ISO code (e.g. 'en'); leave None to auto-detect

        Returns:
            {
                "text": "full transcript",
                "language": "en",
                "language_probability": 0.98,
                "segments": [{"start": 0.0, "end": 2.4, "text": "..."}]
            }
        """
        try:
            # faster-whisper decodes webm/mp3/ogg/wav/m4a etc. internally via
            # PyAV and resamples to 16kHz mono itself — no separate
            # conversion step or system ffmpeg.exe needed.
            segments, info = self.model.transcribe(
                file_path,
                language=language,
                vad_filter=True,  # trims silence, improves accuracy on short clips
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            segment_list = []
            full_text_parts = []
            for seg in segments:
                segment_list.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip()
                })
                full_text_parts.append(seg.text.strip())

            return {
                "text": " ".join(full_text_parts).strip(),
                "language": info.language,
                "language_probability": round(info.language_probability, 3),
                "segments": segment_list
            }

        except Exception as e:
            logger.error(f"STT transcription failed: {e}")
            raise


# Singleton loader — mirrors how you likely load your BLIP model once at
# startup rather than re-loading it on every request.
_stt_engine_instance = None

def get_stt_engine() -> STTEngine:
    global _stt_engine_instance
    if _stt_engine_instance is None:
        _stt_engine_instance = STTEngine(model_size="base", device="cpu", compute_type="int8")
    return _stt_engine_instance
