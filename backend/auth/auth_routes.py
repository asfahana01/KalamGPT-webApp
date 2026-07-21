"""
auth/auth_routes.py — Authentication API endpoints
Covers: Registration, Login, OTP Verification, Session Management, Secure Logout
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
import uuid
import re

from models import db, User, OTP, Session
from auth.auth_utils import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_jwt_token,
    generate_otp,
    send_otp_email,
    token_required,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


# ─── 1. Registration ───────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Step 1 of registration: create unverified user, send OTP.
    Body: { "name": str, "email": str, "password": str }
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or len(name) < 2:
        return jsonify({"error": "Please provide a valid name"}), 400

    if not EMAIL_REGEX.match(email):
        return jsonify({"error": "Please provide a valid email address"}), 400

    is_valid, msg = validate_password_strength(password)
    if not is_valid:
        return jsonify({"error": msg}), 400

    existing = User.query.filter_by(email=email).first()
    if existing and existing.is_verified:
        return jsonify({"error": "An account with this email already exists"}), 409

    if existing:
        existing.name = name
        existing.password_hash = hash_password(password)
        user = existing
    else:
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role="user",
            is_verified=False,
        )
        db.session.add(user)

    db.session.commit()

    otp_code = generate_otp()
    otp = OTP(
        email=email,
        code=otp_code,
        purpose="registration",
        expires_at=OTP.generate_expiry(),
    )
    db.session.add(otp)
    db.session.commit()

    send_otp_email(email, otp_code, purpose="registration")

    return jsonify({
        "message": "Registration initiated. Please check your email for the OTP.",
        "email": email,
    }), 201


# ─── 2. OTP Verification ───────────────────────────────────────────────────────

@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Step 2 of registration: verify OTP, activate account, issue JWT.
    Body: { "email": str, "otp": str }
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    otp_code = data.get("otp", "").strip()

    if not email or not otp_code:
        return jsonify({"error": "Email and OTP are required"}), 400

    otp_record = (
        OTP.query.filter_by(email=email, code=otp_code, is_used=False)
        .order_by(OTP.created_at.desc())
        .first()
    )

    if not otp_record:
        return jsonify({"error": "Invalid OTP"}), 400

    if otp_record.is_expired():
        return jsonify({"error": "OTP has expired. Please request a new one."}), 400

    otp_record.is_used = True

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.is_verified = True
    user.last_login = datetime.utcnow()
    db.session.commit()

    token, session_obj = _create_session(user)
    db.session.add(session_obj)
    db.session.commit()

    return jsonify({
        "message": "Account verified successfully",
        "token": token,
        "user": user.to_dict(),
    }), 200


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    """Resend a fresh OTP if the previous one expired."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "No account found with this email"}), 404

    otp_code = generate_otp()
    otp = OTP(
        email=email,
        code=otp_code,
        purpose="registration",
        expires_at=OTP.generate_expiry(),
    )
    db.session.add(otp)
    db.session.commit()

    send_otp_email(email, otp_code)

    return jsonify({"message": "A new OTP has been sent"}), 200


# ─── 3. Login ───────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login with email + password.
    Body: { "email": str, "password": str }
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not verify_password(password, user.password_hash):
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.is_verified:
        return jsonify({"error": "Please verify your email before logging in"}), 403

    user.last_login = datetime.utcnow()
    db.session.commit()

    token, session_obj = _create_session(user)
    db.session.add(session_obj)
    db.session.commit()

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": user.to_dict(),
    }), 200


# ─── 4. Logout (Secure — revokes token server-side) ──────────────────────────

@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    """Revoke the current session's JWT (secure logout)."""
    session_obj = Session.query.filter_by(token_jti=g.token_jti).first()
    if session_obj:
        session_obj.revoked = True
        db.session.commit()

    return jsonify({"message": "Logged out successfully"}), 200


# ─── 5. Get Current User (session check) ─────────────────────────────────────

@auth_bp.route("/me", methods=["GET"])
@token_required
def get_current_user():
    """Return the currently authenticated user's profile."""
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": user.to_dict()}), 200


# ─── Helper ─────────────────────────────────────────────────────────────────────

def _create_session(user: User):
    """Create a JWT + corresponding Session DB record."""
    jti = str(uuid.uuid4())
    token = create_jwt_token(user.id, user.email, user.role, jti)

    session_obj = Session(
        user_id=user.id,
        token_jti=jti,
        expires_at=datetime.utcnow() + timedelta(hours=24),
        ip_address=request.remote_addr,
    )
    return token, session_obj
