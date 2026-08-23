"""
chat_routes.py — Chat with Kalam AI
"""

import logging
from flask import Blueprint, request, jsonify, g
from io import BytesIO

from models import db, ChatHistory
from auth.auth_utils import optional_token
from utils.security import rate_limit, sanitize_text_input
from ethical.ethical_layer import ethical_layer
from kalam_ai.orchestrator import generate_kalam_response

logger = logging.getLogger(__name__)
chat_bp = Blueprint("chat", __name__, url_prefix="/api")


def register_chat_routes(app, kalam_model, multimodal_engine):
    """Registers chat routes with access to the loaded model."""

    @chat_bp.route("/generate", methods=["POST", "OPTIONS"])
    @optional_token
    @rate_limit(max_requests=20, window_seconds=60)
    def generate():
        """Main text chat endpoint (no RAG)."""
        if request.method == "OPTIONS":
            return "", 200

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        raw_prompt = data.get("prompt", "")
        prompt = sanitize_text_input(raw_prompt, max_length=600)
        session_id = data.get("session_id")

        if not prompt:
            return jsonify({"error": "Prompt cannot be empty"}), 400

        max_tokens = min(int(data.get("max_tokens", 250)), 400)
        temperature = max(0.1, min(float(data.get("temperature", 0.8)), 1.2))

        is_safe, block_reason = ethical_layer.check_input_safety(prompt)
        if not is_safe:
            return jsonify({"response": block_reason, "prompt": prompt, "blocked": True}), 200

        # Generate response through the PDF-aligned layered pipeline.
        # Keep the old model path as a safe fallback during migration.
        try:
            from knowledge.rag_engine import rag_engine
            layered = generate_kalam_response(
                prompt,
                kalam_model,
                rag_engine,
                max_new_tokens=max_tokens,
                temperature=temperature,
            )
            raw_response = layered.response
            sources = layered.sources
            active_layers = layered.active_layers
            verification = layered.verification
        except Exception as exc:
            logger.exception("Layered Kalam pipeline failed; using legacy fallback: %s", exc)
            raw_response = kalam_model.generate(
                user_message=prompt,
                rag_context="",
                max_new_tokens=max_tokens,
                temperature=temperature,
            )
            sources = []
            active_layers = ["personality"]
            verification = {"needs_review": True, "fallback": True}

        ethical_result = ethical_layer.process(prompt, raw_response)
        final_response = ethical_result["response"]

        # Save to database with session
        if g.user_id:
            chat_entry = ChatHistory(
                user_id=g.user_id,
                session_id=session_id,
                prompt=prompt,
                response=final_response,
                retrieved_context="\n\n".join(s.get("text", "") for s in sources) or None,
                input_modality="text",
            )
            db.session.add(chat_entry)
            db.session.commit()

            return jsonify({
                "response": final_response,
                "prompt": prompt,
                "sources": sources,
                "active_layers": active_layers,
                "verification": verification,
                "session_id": session_id,
                "chat_id": chat_entry.id
            }), 200
        
        return jsonify({
            "response": final_response,
            "prompt": prompt,
            "sources": sources,
            "active_layers": active_layers,
            "verification": verification,
        }), 200

    @chat_bp.route("/history", methods=["GET", "OPTIONS"])
    @optional_token
    def get_history():
        """Retrieve chat sessions for the logged-in user."""
        if request.method == "OPTIONS":
            return "", 200

        if not g.user_id:
            return jsonify({"history": []}), 200

        # Get unique sessions (group by session_id)
        sessions = db.session.query(ChatHistory).filter_by(user_id=g.user_id).all()
        
        # Group by session_id
        session_groups = {}
        for chat in sessions:
            session_key = chat.session_id or chat.id
            if session_key not in session_groups:
                session_groups[session_key] = {
                    "id": session_key,
                    "messages": [],
                    "created_at": chat.created_at
                }
            session_groups[session_key]["messages"].append({
                "role": "user",
                "text": chat.prompt
            })
            session_groups[session_key]["messages"].append({
                "role": "kalam",
                "text": chat.response
            })

        # Return sessions (most recent first)
        history = sorted(session_groups.values(), key=lambda x: x["created_at"], reverse=True)
        
        return jsonify({
            "history": [
                {
                    "id": h["id"],
                    "preview": h["messages"][0]["text"][:50] + "...",
                    "message_count": len(h["messages"]),
                    "created_at": h["created_at"].isoformat(),
                }
                for h in history
            ]
        }), 200

    @chat_bp.route("/chat/<chat_id>", methods=["GET", "OPTIONS"])
    @optional_token
    def get_chat(chat_id):
        """Get all messages in a chat session."""
        if request.method == "OPTIONS":
            return "", 200
        
        if not g.user_id:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get all chats in this session
        chats = ChatHistory.query.filter_by(
            user_id=g.user_id,
            session_id=chat_id
        ).all()
        
        if not chats:
            chat = ChatHistory.query.filter_by(id=chat_id, user_id=g.user_id).first()
            if not chat:
                return jsonify({"error": "Chat not found"}), 404
            chats = [chat]
        
        # Build conversation
        messages = []
        for chat in chats:
            messages.append({"role": "user", "text": chat.prompt})
            messages.append({"role": "kalam", "text": chat.response})
        
        return jsonify({"chat": messages}), 200

    @chat_bp.route("/text-to-speech", methods=["POST", "OPTIONS"])
    @optional_token
    def text_to_speech():
        """Convert text response to speech (Kalam's voice)."""
        if request.method == "OPTIONS":
            return "", 200

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        text = data.get("text", "")
        if not text:
            return jsonify({"error": "Text is required"}), 400

        try:
            from gtts import gTTS
            
            # Generate speech with gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            
            # Create in-memory audio file
            audio_buffer = BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            return audio_buffer.getvalue(), 200, {
                'Content-Type': 'audio/mpeg',
                'Content-Disposition': 'inline; filename="kalam_response.mp3"'
            }
        
        except ImportError:
            logger.warning("gTTS not installed")
            return jsonify({
                "error": "Voice synthesis not available. Please install gtts: pip install gtts"
            }), 500
        
        except Exception as e:
            logger.error(f"Text-to-speech error: {str(e)}")
            return jsonify({"error": "Failed to generate speech"}), 500

    app.register_blueprint(chat_bp)