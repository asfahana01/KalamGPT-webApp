"""
chat_routes.py — Simplified version without RAG
"""

import logging
from flask import Blueprint, request, jsonify, g  # Make sure 'g' is imported

from models import db, ChatHistory
from auth.auth_utils import optional_token
from utils.security import rate_limit, sanitize_text_input
from ethical.ethical_layer import ethical_layer

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

        if not prompt:
            return jsonify({"error": "Prompt cannot be empty"}), 400

        max_tokens = min(int(data.get("max_tokens", 250)), 400)
        temperature = max(0.1, min(float(data.get("temperature", 0.8)), 1.2))

        is_safe, block_reason = ethical_layer.check_input_safety(prompt)
        if not is_safe:
            return jsonify({"response": block_reason, "prompt": prompt, "blocked": True}), 200

        # Generate without RAG
        raw_response = kalam_model.generate(
            user_message=prompt,
            rag_context="",
            max_new_tokens=max_tokens,
            temperature=temperature,
        )

        ethical_result = ethical_layer.process(prompt, raw_response)
        final_response = ethical_result["response"]

        if g.user_id:
            chat_entry = ChatHistory(
                user_id=g.user_id,
                prompt=prompt,
                response=final_response,
                retrieved_context=None,
                input_modality="text",
            )
            db.session.add(chat_entry)
            db.session.commit()

        return jsonify({
            "response": final_response,
            "prompt": prompt,
            "sources": [],
        }), 200

    @chat_bp.route("/history", methods=["GET", "OPTIONS"])
    @optional_token
    def get_history():
        """Retrieve chat history for the logged-in user."""
        if request.method == "OPTIONS":
            return "", 200

        if not g.user_id:
            return jsonify({"history": []}), 200

        entries = (
            ChatHistory.query.filter_by(user_id=g.user_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(50)
            .all()
        )

        return jsonify({
            "history": [
                {
                    "id": e.id,
                    "prompt": e.prompt,
                    "response": e.response,
                    "input_modality": e.input_modality,
                    "created_at": e.created_at.isoformat(),
                }
                for e in reversed(entries)
            ]
        }), 200
    
    @chat_bp.route("/chat/<int:chat_id>", methods=["GET", "OPTIONS"])
    @optional_token
    def get_chat(chat_id):
        """Get a specific chat conversation by ID."""
        if request.method == "OPTIONS":
            return "", 200
        
        if not g.user_id:
            return jsonify({"error": "Unauthorized"}), 401
        
        chat = ChatHistory.query.filter_by(id=chat_id, user_id=g.user_id).first()
        
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
        
        return jsonify({
            "chat": [
                {"role": "user", "text": chat.prompt},
                {"role": "kalam", "text": chat.response}
            ]
        }), 200

    app.register_blueprint(chat_bp)