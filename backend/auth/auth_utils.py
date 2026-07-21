"""
auth/auth_utils.py — Core authentication utilities
Covers: Password hashing, JWT creation/verification, OTP generation, email sending
"""

import bcrypt
import jwt
import random
import string
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g

# ─── Config (loaded from environment — NEVER hardcode secrets) ───────────────
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")      # your email
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # app-specific password, NOT your real password


# ─── Password Hashing (bcrypt — industry standard, salted automatically) ─────

def hash_password(plain_password: str) -> str:
    """Hash a password with bcrypt. Never store plain text passwords."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Enforce minimum password security requirements.
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, ""


# ─── JWT Token Management ─────────────────────────────────────────────────────

def create_jwt_token(user_id: str, email: str, role: str, jti: str) -> str:
    """
    Create a signed JWT token for an authenticated session.
    'jti' (JWT ID) allows us to revoke individual tokens (secure logout).
    """
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "jti": jti,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict | None:
    """Decode and verify a JWT token. Returns None if invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ─── OTP Generation & Email Delivery ──────────────────────────────────────────

def generate_otp() -> str:
    """Generate a 6-digit numeric OTP."""
    return "".join(random.choices(string.digits, k=6))


def send_otp_email(to_email: str, otp_code: str, purpose: str = "registration") -> bool:
    """
    Send OTP via email using SMTP.
    In development without SMTP configured, logs OTP to console instead.
    """
    subject = "Your KalamGPT Verification Code"
    body = f"""
    Namaste,

    Your KalamGPT verification code is: {otp_code}

    This code will expire in 10 minutes.
    If you did not request this, please ignore this email.

    "You have to dream before your dreams can come true." — Dr. A.P.J. Abdul Kalam
    """

    if not SMTP_USER or not SMTP_PASSWORD:
        # Development fallback — print to console instead of failing
        print(f"\n{'='*50}")
        print(f"📧 [DEV MODE] OTP for {to_email}: {otp_code}")
        print(f"{'='*50}\n")
        return True

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send OTP email: {e}")
        return False


# ─── Auth Decorators (Route Protection) ───────────────────────────────────────

def token_required(f):
    """
    Decorator to protect routes — requires valid JWT in Authorization header.
    Usage: Authorization: Bearer <token>
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ")[1]
        payload = decode_jwt_token(token)

        if payload is None:
            return jsonify({"error": "Token is invalid or expired"}), 401

        # Attach user info to Flask's request context
        g.user_id = payload["sub"]
        g.user_email = payload["email"]
        g.user_role = payload["role"]
        g.token_jti = payload["jti"]

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """
    Decorator to protect admin-only routes.
    Must be used AFTER @token_required.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if getattr(g, "user_role", None) != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


def optional_token(f):
    """
    Decorator for routes that work for both guests and logged-in users.
    Attaches user info if a valid token is present, otherwise proceeds as guest.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        g.user_id = None
        g.user_email = None
        g.user_role = "guest"

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = decode_jwt_token(token)
            if payload:
                g.user_id = payload["sub"]
                g.user_email = payload["email"]
                g.user_role = payload["role"]

        return f(*args, **kwargs)
    return decorated
