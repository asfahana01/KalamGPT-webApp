"""
app.py — KalamGPT Full System Entry Point

Wires together every layer from the system architecture:
  1.1 User Authentication Module
  1.2 User Interaction Layer      → served by /api/* endpoints, consumed by React
  1.3 Input Processing Layer      → sanitize_text_input, image/audio decoding
  1.4 Knowledge Repository        → knowledge/rag_engine.py
  1.5 RAG Layer                   → knowledge/rag_engine.py
  1.6 Intelligence Processing     → model.py
  1.7 Ethical Alignment Layer     → ethical/ethical_layer.py
  1.8 Multimodal Analysis Layer   → multimodal/multimodal_engine.py
  1.9 Output Generation Layer     → text + audio (TTS) in chat_routes.py
  2.0 Feedback & Learning Layer   → feedback/feedback_routes.py
"""

import os
import logging
from flask import Flask, jsonify #yellow underline is showing under flask
from flask_cors import CORS #yellow underline is showing under flask_cors
from dotenv import load_dotenv

load_dotenv()  # loads .env file — NEVER commit .env to git

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# App & Database Setup
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///kalamgpt.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB max upload (images/audio)

from models import db
db.init_app(app)

# Create database tables
with app.app_context():
    db.create_all()

# ─────────────────────────────────────────────────────────────────────────────
# CORS — restrict to known frontend origins only
# ─────────────────────────────────────────────────────────────────────────────

CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:3000",
            os.getenv("FRONTEND_URL", "*"),
        ]
    }
})

# ─────────────────────────────────────────────────────────────────────────────
# Security headers (applied to every response)
# ─────────────────────────────────────────────────────────────────────────────

from utils.security import apply_security_headers
app.after_request(apply_security_headers)

# ─────────────────────────────────────────────────────────────────────────────
# Register Authentication Module (1.1)
# ─────────────────────────────────────────────────────────────────────────────

from auth.auth_routes import auth_bp
app.register_blueprint(auth_bp)

# ─────────────────────────────────────────────────────────────────────────────
# Register Feedback & Learning Layer (2.0)
# ─────────────────────────────────────────────────────────────────────────────

from feedback.feedback_routes import feedback_bp
app.register_blueprint(feedback_bp)

# ─────────────────────────────────────────────────────────────────────────────
# Load Intelligence Processing Layer (1.6) — the fine-tuned model
# ─────────────────────────────────────────────────────────────────────────────

from model import KalamGPT

MODEL_PATH = os.getenv("MODEL_PATH", "./kalam_model")
logger.info(f"Initialising KalamGPT model from: {MODEL_PATH}")
kalam_model = KalamGPT(MODEL_PATH)

# ─────────────────────────────────────────────────────────────────────────────
# Load Multimodal Analysis Layer (1.7) — lazy-loaded on first use
# ─────────────────────────────────────────────────────────────────────────────

from multimodal.multimodal_engine import multimodal_engine

# ─────────────────────────────────────────────────────────────────────────────
# Register Chat Routes (wires RAG + Ethical Layer + Model together)
# ─────────────────────────────────────────────────────────────────────────────

from chat_routes import register_chat_routes
register_chat_routes(app, kalam_model, multimodal_engine)

# ─────────────────────────────────────────────────────────────────────────────
# Health & Root Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    from knowledge.rag_engine import rag_engine
    return jsonify({
        "status": "ok",
        "model": kalam_model.health_check(),
        "knowledge_base": rag_engine.get_stats(),
    }), 200


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": "KalamGPT API is running",
        "endpoints": {
            "auth": "/api/auth/*",
            "chat": "/api/generate",
            "feedback": "/api/feedback/*",
            "health": "/api/health",
        },
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Database Initialization
# ─────────────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    logger.info("✅ Database tables created/verified")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
