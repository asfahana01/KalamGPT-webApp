"""
models.py — Database models for KalamGPT
Uses SQLite (file-based, zero-setup) via SQLAlchemy ORM.
Covers: Users, Sessions, Feedback, Knowledge Sources, Chat History
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import uuid

db = SQLAlchemy()


class User(db.Model):
    """
    1.1 User Authentication Module — User table
    Stores registered users with hashed passwords and role-based access.
    """
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)  # bcrypt hash — never plain text
    role = db.Column(db.String(20), default="user")  # 'user' or 'admin' — Role-Based Access Control
    is_verified = db.Column(db.Boolean, default=False)  # becomes True after OTP verification
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat(),
        }


class OTP(db.Model):
    """
    Stores one-time passwords for email verification / login 2FA.
    OTPs expire after 10 minutes.
    """
    __tablename__ = "otps"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    purpose = db.Column(db.String(20), nullable=False)  # 'registration' or 'login'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @staticmethod
    def generate_expiry():
        return datetime.utcnow() + timedelta(minutes=10)


class Session(db.Model):
    """
    Session Management — tracks active JWT-issued sessions.
    Allows secure logout (token revocation) even though JWTs are stateless.
    """
    __tablename__ = "sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    token_jti = db.Column(db.String(36), unique=True, nullable=False)  # JWT ID claim
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, default=False)
    ip_address = db.Column(db.String(45), nullable=True)


class ChatHistory(db.Model):
    """
    Stores conversation turns for logged-in users.
    Also feeds the Continuous Learning Pipeline (Data Logging & Monitoring stage).
    """
    __tablename__ = "chat_history"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)  # nullable for guest use
    session_id = db.Column(db.String(36), nullable=True)
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    retrieved_context = db.Column(db.Text, nullable=True)  # RAG chunks used, for auditing
    input_modality = db.Column(db.String(20), default="text")  # 'text', 'voice', 'image'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Feedback(db.Model):
    """
    1.9 Feedback & Learning Layer
    Stores user ratings and correction suggestions for continuous improvement.
    """
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chat_history.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=True)  # 1 = thumbs down, 5 = thumbs up (or 1-5 scale)
    correction = db.Column(db.Text, nullable=True)  # user-suggested better response
    error_report = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class KnowledgeSource(db.Model):
    """
    1.4 Knowledge Repository Layer — metadata for documents indexed into the vector DB.
    """
    __tablename__ = "knowledge_sources"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    source_type = db.Column(db.String(50), nullable=False)  # 'book', 'speech', 'article', 'vision_doc'
    file_path = db.Column(db.String(500), nullable=True)
    chunk_count = db.Column(db.Integer, default=0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_indexed_at = db.Column(db.DateTime, nullable=True)
