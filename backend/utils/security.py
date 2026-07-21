"""
utils/security.py — Security hardening utilities
Covers: Rate limiting, security headers, input sanitization

This is the practical, real-world version of "encryption/security" —
literal source code encryption isn't possible for a running server,
but these measures are what actually protect production systems.
"""

import time
import re
from collections import defaultdict
from functools import wraps
from flask import request, jsonify

# ─── Simple in-memory rate limiter ─────────────────────────────────────────
# For production at scale, replace with Redis-backed rate limiting.
# This in-memory version is sufficient for a college major project demo.

_request_log = defaultdict(list)


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Decorator to rate-limit an endpoint per IP address.
    Example: @rate_limit(max_requests=5, window_seconds=60)
             → max 5 requests per IP per minute
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            now = time.time()

            # Clean up old requests outside the window
            _request_log[ip] = [
                t for t in _request_log[ip] if now - t < window_seconds
            ]

            if len(_request_log[ip]) >= max_requests:
                return jsonify({
                    "error": "Too many requests. Please slow down and try again shortly."
                }), 429

            _request_log[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ─── Security headers (applied globally via after_request) ────────────────

def apply_security_headers(response):
    """
    Add standard security headers to every response.
    Register with: app.after_request(apply_security_headers)
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    # Strict-Transport-Security only makes sense once HTTPS is enforced (Render provides this)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ─── Input sanitization ─────────────────────────────────────────────────────

# Basic SQL-injection-pattern detector (defense in depth — SQLAlchemy ORM
# already parameterizes queries, but this catches obviously malicious input
# early and is worth citing in a security-focused report).
SQLI_PATTERNS = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|EXEC)\b|--|;|/\*|\*/)",
    re.IGNORECASE,
)

XSS_PATTERNS = re.compile(
    r"(<script|javascript:|onerror=|onload=|<iframe)",
    re.IGNORECASE,
)


def sanitize_text_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize free-text user input before it reaches the model or database.
    Strips dangerous patterns and enforces length limits.
    """
    if not text:
        return ""

    text = text.strip()[:max_length]

    if SQLI_PATTERNS.search(text):
        text = SQLI_PATTERNS.sub("", text)

    if XSS_PATTERNS.search(text):
        text = XSS_PATTERNS.sub("", text)

    return text


def validate_file_upload(filename: str, allowed_extensions: set) -> bool:
    """Validate uploaded file extensions to prevent malicious file uploads."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions
