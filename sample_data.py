"""Populate the practicelog database with sample sessions."""
from __future__ import annotations

from datetime import datetime, timedelta
import random

from app import app, db, get_or_create_tag, get_or_create_topic
from models import Instrument, Session, SessionTopic, TopicTag

TOPIC_SETS = [
    ("Escalas mayores", "Repasar digitación en tercera posición", ["técnica"]),
    ("Arpegios", "Enfoque en ritmo swing", ["ritmo"]),
    ("Lectura a primera vista", "Piezas fáciles nivel 2", ["lectura"]),
    ("Improvisación", "Modo dórico sobre II-V-I", ["creatividad", "jazz"]),
    ("Repertorio", "Estudio Nº5 - tempo 80", ["repertorio"]),
]


def create_session(day_offset: int, duration: int, instrument: Instrument) -> None:
    """Create a session with deterministic but varied data."""

    started_at = datetime.now() - timedelta(days=day_offset, hours=random.randint(0, 3))
    description = f"Sesión de práctica #{day_offset + 1}"

    session = Session(
        started_at=started_at,
        duration_min=duration,
        description=description,
        instrument=instrument,
    )
    db.session.add(session)
    db.session.flush()

    chosen_topics = random.sample(TOPIC_SETS, k=2)
    for name, note, tags in chosen_topics:
        topic = get_or_create_topic(name)
        session_topic = SessionTopic(session=session, topic=topic, note=note)
        db.session.add(session_topic)
        for tag_name in tags:
            tag = get_or_create_tag(tag_name)
            existing = TopicTag.query.filter_by(topic_id=topic.id, tag_id=tag.id).one_or_none()
            if existing is None:
                db.session.add(TopicTag(topic=topic, tag=tag))

    db.session.commit()


def main() -> None:
    """Bootstrap the database with deterministic instruments and sessions."""

    with app.app_context():
        instrument = Instrument.query.filter_by(name="Guitarra").first()
        if instrument is None:
            instrument = Instrument(name="Guitarra")
            db.session.add(instrument)
            db.session.commit()

        SessionTopic.query.delete()
        Session.query.delete()
        db.session.commit()

        for offset in range(5):
            create_session(offset, duration=45 + offset * 5, instrument=instrument)

        print("Base de datos poblada con sesiones de ejemplo ✅")


if __name__ == "__main__":
    main()
