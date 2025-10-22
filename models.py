"""Database models for the practicelog application."""
from __future__ import annotations

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, Index
from sqlalchemy.orm import relationship


# Global SQLAlchemy instance initialized in app.py
# pylint: disable=invalid-name
# It is kept here so models can be imported without circular references.
db = SQLAlchemy()


class TimestampMixin:
    """Mixin providing created and updated timestamps."""

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Instrument(db.Model, TimestampMixin):
    """Instrument seed table."""

    __tablename__ = "instruments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    sessions = relationship("Session", back_populates="instrument", lazy="dynamic")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Instrument {self.name}>"


class Session(db.Model, TimestampMixin):
    """Practice session entry."""

    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_min = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)

    instrument_id = db.Column(db.Integer, db.ForeignKey("instruments.id"), nullable=False)

    instrument = relationship("Instrument", back_populates="sessions")
    topics = relationship(
        "SessionTopic",
        cascade="all, delete-orphan",
        back_populates="session",
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_sessions_started_at", "started_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Session {self.id} {self.started_at}>"


class Topic(db.Model, TimestampMixin):
    """Practice topics such as scales or pieces."""

    __tablename__ = "topics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)

    session_topics = relationship("SessionTopic", back_populates="topic", lazy="dynamic")
    tags = relationship("TopicTag", cascade="all, delete-orphan", back_populates="topic")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Topic {self.name}>"


class Tag(db.Model, TimestampMixin):
    """Free-form tags linked to topics."""

    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True, index=True)

    topics = relationship("TopicTag", cascade="all, delete-orphan", back_populates="tag")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Tag {self.name}>"


class SessionTopic(db.Model, TimestampMixin):
    """Association between sessions and topics storing notes."""

    __tablename__ = "session_topics"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    note = db.Column(db.Text, nullable=True)

    session = relationship("Session", back_populates="topics")
    topic = relationship("Topic", back_populates="session_topics")

    __table_args__ = (
        UniqueConstraint("session_id", "topic_id", name="uq_session_topic"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SessionTopic session={self.session_id} topic={self.topic_id}>"


class TopicTag(db.Model, TimestampMixin):
    """Many-to-many relation between topics and tags."""

    __tablename__ = "topic_tags"

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"), nullable=False)

    topic = relationship("Topic", back_populates="tags")
    tag = relationship("Tag", back_populates="topics")

    __table_args__ = (
        UniqueConstraint("topic_id", "tag_id", name="uq_topic_tag"),
        Index("ix_topic_tag_topic", "topic_id"),
        Index("ix_topic_tag_tag", "tag_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<TopicTag topic={self.topic_id} tag={self.tag_id}>"


def init_db(app) -> None:
    """Create all tables and seed initial data."""

    with app.app_context():
        db.create_all()
        seed_instruments()


def seed_instruments() -> None:
    """Seed default instruments if not present."""

    existing = {name for (name,) in db.session.query(Instrument.name).all()}
    for name in ("Guitarra", "Piano", "Violín"):
        if name not in existing:
            db.session.add(Instrument(name=name))
    db.session.commit()
