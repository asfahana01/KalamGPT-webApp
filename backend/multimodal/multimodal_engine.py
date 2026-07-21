"""
multimodal/multimodal_engine.py — 1.7 Multimodal Analysis Layer + Input/Output modalities

Covers:
  - Image understanding (using a pretrained BLIP image-captioning model)
  - Voice input (speech-to-text via SpeechRecognition + Google Web Speech API)
  - Voice output (text-to-speech via gTTS)

Design note: We use pretrained models (BLIP for vision, not a custom CNN
trained from scratch) — this is standard practice and exactly what real
production systems do. Training a CNN from scratch would need a huge
labeled image dataset we don't have; transfer learning is the correct
and citable approach here.
"""

import os
import io
import base64
import tempfile
import logging

logger = logging.getLogger(__name__)


class MultimodalEngine:
    """
    Handles image captioning and voice transcription/synthesis.
    Models are lazy-loaded (only loaded into memory on first use)
    to keep startup time and idle memory usage low.
    """

    def __init__(self):
        self._blip_processor = None
        self._blip_model = None
        self._recognizer = None

    # ── Image Understanding (CNN / Vision-Language Model) ────────────────────

    def _load_image_model(self):
        """Lazy-load the BLIP image captioning model (pretrained, ~990MB)."""
        if self._blip_model is None:
            logger.info("Loading BLIP image captioning model...")
            from transformers import BlipProcessor, BlipForConditionalGeneration
            self._blip_processor = BlipProcessor.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )
            self._blip_model = BlipForConditionalGeneration.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )
            logger.info("✅ BLIP model loaded")

    def caption_image(self, image_bytes: bytes) -> str:
        """
        Generate a caption/description for an uploaded image.
        Used to let users ask Kalam GPT about images (e.g. "what do you see here?").
        """
        from PIL import Image

        self._load_image_model()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self._blip_processor(image, return_tensors="pt")
        output = self._blip_model.generate(**inputs, max_new_tokens=50)
        caption = self._blip_processor.decode(output[0], skip_special_tokens=True)

        return caption

    def build_image_prompt(self, caption: str, user_question: str = "") -> str:
        """
        Convert an image caption into a text prompt the language model can respond to,
        in Kalam's voice.
        """
        if user_question:
            return f"[User shared an image showing: {caption}] {user_question}"
        return f"[User shared an image showing: {caption}] What do you think about this?"

    # ── Voice Input (Speech-to-Text) ──────────────────────────────────────────

    def _load_speech_recognizer(self):
        if self._recognizer is None:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()

    def transcribe_audio(self, audio_bytes: bytes, audio_format: str = "wav") -> str:
        """
        Convert speech audio to text using Google's free Web Speech API
        (via the speech_recognition library — no API key required for basic use).
        """
        import speech_recognition as sr

        self._load_speech_recognizer()

        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with sr.AudioFile(tmp_path) as source:
                audio_data = self._recognizer.record(source)
                text = self._recognizer.recognize_google(audio_data)
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return ""
        finally:
            os.unlink(tmp_path)

    # ── Voice Output (Text-to-Speech) ─────────────────────────────────────────

    def synthesize_speech(self, text: str, lang: str = "en") -> bytes:
        """
        Convert text response to speech audio using gTTS (Google Text-to-Speech).
        Returns raw MP3 bytes, which the frontend can play directly.
        """
        from gtts import gTTS

        # Truncate very long responses for reasonable audio length
        text_to_speak = text[:500]

        tts = gTTS(text=text_to_speak, lang=lang, slow=False)

        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)

        return buffer.read()

    def synthesize_speech_base64(self, text: str, lang: str = "en") -> str:
        """Convenience wrapper: returns base64-encoded audio for JSON API responses."""
        audio_bytes = self.synthesize_speech(text, lang)
        return base64.b64encode(audio_bytes).decode("utf-8")


# Singleton instance
multimodal_engine = MultimodalEngine()
