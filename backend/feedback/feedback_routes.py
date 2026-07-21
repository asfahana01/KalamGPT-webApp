"""
feedback/feedback_routes.py — 1.9 Feedback & Learning Layer

Collects:
  - User ratings (thumbs up/down)
  - Query correction suggestions
  - Response quality feedback
  - Error reports

This data feeds the Continuous Learning Pipeline (stages 1-2 of the
automatic model update mechanism in the architecture diagram).
"""

from flask import Blueprint, request, jsonify, g
from models import db, Feedback, ChatHistory
from auth.auth_utils import optional_token

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


@feedback_bp.route("/rate", methods=["POST"])
@optional_token
def rate_response():
    """
    Submit a rating for a specific chat response.
    Body: { "chat_id": int, "rating": int (1-5), "correction": str (optional) }
    """
    data = request.get_json(silent=True) or {}
    chat_id = data.get("chat_id")
    rating = data.get("rating")
    correction = data.get("correction", "").strip() or None

    if chat_id is None or rating is None:
        return jsonify({"error": "chat_id and rating are required"}), 400

    if not (1 <= int(rating) <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    chat = ChatHistory.query.get(chat_id)
    if not chat:
        return jsonify({"error": "Chat entry not found"}), 404

    feedback = Feedback(
        chat_id=chat_id,
        user_id=g.user_id,  # None if guest
        rating=rating,
        correction=correction,
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"message": "Thank you for your feedback!", "feedback_id": feedback.id}), 201


@feedback_bp.route("/report-error", methods=["POST"])
@optional_token
def report_error():
    """
    Report an issue with a response (factual error, inappropriate content, etc.)
    Body: { "chat_id": int, "error_report": str }
    """
    data = request.get_json(silent=True) or {}
    chat_id = data.get("chat_id")
    error_report = data.get("error_report", "").strip()

    if chat_id is None or not error_report:
        return jsonify({"error": "chat_id and error_report are required"}), 400

    chat = ChatHistory.query.get(chat_id)
    if not chat:
        return jsonify({"error": "Chat entry not found"}), 404

    feedback = Feedback(
        chat_id=chat_id,
        user_id=g.user_id,
        error_report=error_report,
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"message": "Error report submitted. Thank you for helping us improve."}), 201


@feedback_bp.route("/stats", methods=["GET"])
def feedback_stats():
    """
    Public aggregate feedback statistics — useful for your project report's
    'Continuous Learning Pipeline' evidence section.
    """
    total = Feedback.query.count()
    avg_rating_result = db.session.query(db.func.avg(Feedback.rating)).filter(
        Feedback.rating.isnot(None)
    ).scalar()

    avg_rating = round(avg_rating_result, 2) if avg_rating_result else None

    return jsonify({
        "total_feedback_entries": total,
        "average_rating": avg_rating,
    }), 200
