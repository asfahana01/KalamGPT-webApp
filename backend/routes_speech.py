"""
routes_speech.py
Flask blueprint exposing the Speech-to-Text endpoint for KalamGPT.

Register this in your main app.py alongside your existing blueprints:

    from routes_speech import speech_bp
    app.register_blueprint(speech_bp)

Adjust the `token_required` import below to match whatever your existing
JWT auth decorator is actually called/located at in your v2 backend.
"""

import os
import tempfile
import logging
from flask import Blueprint, request, jsonify
from stt_engine import get_stt_engine
from auth.auth_utils import token_required

logger = logging.getLogger(__name__)

speech_bp = Blueprint("speech", __name__, url_prefix="/api")

ALLOWED_EXTENSIONS = {"wav", "mp3", "ogg", "webm", "m4a", "flac"}
MAX_AUDIO_SIZE_MB = 25


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@speech_bp.route("/speech-to-text", methods=["POST"])
@token_required  # remove this line if you want the endpoint public/unauthenticated
def speech_to_text(current_user=None):
    """
    Accepts multipart/form-data:
        - 'audio' (file, required): the recorded audio clip
        - 'language' (str, optional): ISO code like 'en' to skip auto-detect

    Returns JSON:
        { "text": "...", "language": "en", "language_probability": 0.98, "segments": [...] }
    """
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided. Use form field 'audio'."}), 400

    audio_file = request.files["audio"]

    if audio_file.filename == "":
        return jsonify({"error": "Empty filename."}), 400

    if not _allowed_file(audio_file.filename):
        return jsonify({"error": f"Unsupported format. Allowed: {sorted(ALLOWED_EXTENSIONS)}"}), 400

    audio_file.seek(0, os.SEEK_END)
    size_mb = audio_file.tell() / (1024 * 1024)
    audio_file.seek(0)
    if size_mb > MAX_AUDIO_SIZE_MB:
        return jsonify({"error": f"File too large ({size_mb:.1f}MB). Max {MAX_AUDIO_SIZE_MB}MB."}), 413

    tmp_path = None
    try:
        suffix = os.path.splitext(audio_file.filename)[1]
        tmp_path = tempfile.mktemp(suffix=suffix)
        audio_file.save(tmp_path)

        language = request.form.get("language") or None

        engine = get_stt_engine()
        result = engine.transcribe(tmp_path, language=language)

        logger.info(f"STT success — {len(result['text'])} chars, lang={result['language']}")
        return jsonify(result), 200

    except Exception as e:
        logger.exception("STT endpoint error")
        return jsonify({"error": "Transcription failed.", "detail": str(e)}), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
