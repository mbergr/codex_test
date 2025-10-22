"""Main Flask application for the practicelog project."""
from __future__ import annotations

import csv
import io
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from dateutil import tz
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from pydantic import BaseModel, ValidationError, validator

from models import (
    Instrument,
    Session,
    SessionTopic,
    Tag,
    Topic,
    TopicTag,
    db,
    init_db,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "practice.db")


class TopicInput(BaseModel):
    """Representation of a topic submitted from forms."""

    name: str
    note: str | None = None

    @validator("name")
    def name_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El tema no puede estar vacío")
        return value.strip()


class SessionInput(BaseModel):
    """Validated practice session payload."""

    started_at: datetime
    duration_min: int
    instrument_id: int
    description: str | None = None
    topics: List[TopicInput]
    tags: List[str] = []

    @validator("duration_min")
    def duration_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("La duración debe ser positiva")
        return value

    @validator("topics")
    def at_least_one_topic(cls, value: List[TopicInput]) -> List[TopicInput]:
        if not value:
            raise ValueError("Añade al menos un tema")
        return value


# Flask application factory -------------------------------------------------
app = Flask(__name__)
app.config.update(
    SECRET_KEY="practicelog-secret-key",
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_PATH}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    JSON_SORT_KEYS=False,
)

os.makedirs(DATA_DIR, exist_ok=True)

db.init_app(app)
init_db(app)


# Utility helpers -----------------------------------------------------------
def parse_datetime(value: str) -> datetime:
    """Parse ISO datetime strings coming from the HTML input."""

    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("Fecha inválida") from exc


def get_local_timezone() -> tz.tzlocal:
    """Return the local timezone object."""

    return tz.tzlocal()


def get_or_create_topic(name: str) -> Topic:
    topic = Topic.query.filter_by(name=name).one_or_none()
    if topic is None:
        topic = Topic(name=name)
        db.session.add(topic)
        db.session.flush()
    return topic


def get_or_create_tag(name: str) -> Tag:
    tag = Tag.query.filter_by(name=name).one_or_none()
    if tag is None:
        tag = Tag(name=name)
        db.session.add(tag)
        db.session.flush()
    return tag


def streak_info() -> Tuple[int, datetime | None, datetime | None]:
    """Calculate the current streak of consecutive practice days."""

    sessions = (
        Session.query.order_by(Session.started_at.desc())
        .with_entities(Session.started_at)
        .all()
    )
    if not sessions:
        return 0, None, None

    tzinfo = get_local_timezone()
    today = datetime.now(tzinfo).date()

    streak = 0
    streak_start = None
    streak_end = None
    previous_day = None

    for (started_at,) in sessions:
        day = started_at.date()
        if previous_day is None:
            # Start counting from today backwards.
            if (today - day).days > 0:
                today_offset = (today - day).days
                if today_offset > 0:
                    # Missed the day immediately before today: break.
                    if today_offset > 1:
                        break
            streak = 1
            streak_start = day
            streak_end = day
            previous_day = day
            continue

        diff = (previous_day - day).days
        if diff == 0:
            continue
        if diff == 1:
            streak += 1
            streak_start = day
            previous_day = day
        else:
            break

    return streak, streak_start, streak_end


def aggregate_time_by_topic(sessions: List[Session]) -> Dict[str, float]:
    """Distribute session duration by topic as per requirements."""

    totals: Dict[str, float] = defaultdict(float)
    for session in sessions:
        topic_count = len(session.topics)
        if topic_count == 0:
            continue
        share = session.duration_min / topic_count
        for session_topic in session.topics:
            totals[session_topic.topic.name] += share
    return totals


def aggregate_time_by_tag(sessions: List[Session]) -> Dict[str, float]:
    """Aggregate distributed time per tag using topic associations."""

    totals: Dict[str, float] = defaultdict(float)
    for session in sessions:
        topic_count = len(session.topics)
        if topic_count == 0:
            continue
        share = session.duration_min / topic_count
        for session_topic in session.topics:
            topic = session_topic.topic
            if not topic.tags:
                continue
            for topic_tag in topic.tags:
                totals[topic_tag.tag.name] += share
    return totals


def weekly_sessions() -> List[Session]:
    """Return sessions from the last seven days."""

    since = datetime.now() - timedelta(days=7)
    return (
        Session.query.filter(Session.started_at >= since)
        .order_by(Session.started_at.desc())
        .all()
    )


def serialize_session(session: Session) -> Dict:
    """Serialize a session to JSON."""

    return {
        "id": session.id,
        "started_at": session.started_at.isoformat(),
        "duration_min": session.duration_min,
        "instrument": session.instrument.name,
        "description": session.description,
        "topics": [
            {
                "name": st.topic.name,
                "note": st.note,
                "tags": [tt.tag.name for tt in st.topic.tags],
            }
            for st in session.topics
        ],
    }


# Routes -------------------------------------------------------------------
@app.route("/")
def dashboard() -> str:
    """Render dashboard with quick stats."""

    sessions = Session.query.order_by(Session.started_at.desc()).all()
    last_week_sessions = weekly_sessions()

    streak, streak_start, streak_end = streak_info()
    weekly_total = sum(session.duration_min for session in last_week_sessions)
    topic_totals = aggregate_time_by_topic(last_week_sessions)
    top_topics = sorted(topic_totals.items(), key=lambda x: x[1], reverse=True)[:5]

    chart_labels = [name for name, _ in top_topics]
    chart_data = [round(minutes, 2) for _, minutes in top_topics]

    return render_template(
        "dashboard.html",
        streak=streak,
        streak_start=streak_start,
        streak_end=streak_end,
        weekly_total=weekly_total,
        top_topics=top_topics,
        chart_labels=chart_labels,
        chart_data=chart_data,
        total_sessions=len(sessions),
    )


@app.route("/sessions")
def sessions_list() -> str:
    """List practice sessions with filters."""

    query = Session.query.order_by(Session.started_at.desc())

    search = request.args.get("q")
    topic_name = request.args.get("topic")
    tag_name = request.args.get("tag")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    if search:
        query = query.filter(Session.description.ilike(f"%{search}%"))

    if topic_name:
        query = query.join(SessionTopic).join(Topic).filter(Topic.name == topic_name)

    if tag_name:
        query = (
            query.join(SessionTopic)
            .join(Topic)
            .join(TopicTag)
            .join(Tag)
            .filter(Tag.name == tag_name)
        )

    if date_from:
        start_date = datetime.fromisoformat(date_from)
        query = query.filter(Session.started_at >= start_date)

    if date_to:
        end_date = datetime.fromisoformat(date_to)
        query = query.filter(Session.started_at <= end_date)

    sessions = query.all()
    session_tags = {
        session.id: sorted(
            {
                topic_tag.tag.name
                for session_topic in session.topics
                for topic_tag in session_topic.topic.tags
            }
        )
        for session in sessions
    }

    all_topics = Topic.query.order_by(Topic.name).all()
    all_tags = Tag.query.order_by(Tag.name).all()

    return render_template(
        "sessions_list.html",
        sessions=sessions,
        filters={
            "q": search or "",
            "topic": topic_name or "",
            "tag": tag_name or "",
            "from": date_from or "",
            "to": date_to or "",
        },
        topics=all_topics,
        tags=all_tags,
        session_tags=session_tags,
    )


@app.route("/sessions/new")
def new_session() -> str:
    """Render the new session form."""

    instruments = Instrument.query.order_by(Instrument.name).all()
    topic_names = [topic.name for topic in Topic.query.order_by(Topic.name)]
    tag_names = [tag.name for tag in Tag.query.order_by(Tag.name)]

    return render_template(
        "session_form.html",
        instruments=instruments,
        topic_names=topic_names,
        tag_names=tag_names,
        default_started_at=datetime.now().strftime("%Y-%m-%dT%H:%M"),
        uuid4=uuid.uuid4,
    )


@app.route("/sessions/topic-row")
def topic_row() -> str:
    """Return a topic form row for htmx requests."""

    uid = uuid.uuid4().hex
    return render_template("_topic_fields.html", uid=uid, topic=None)


@app.route("/sessions", methods=["POST"])
def create_session() -> Response:
    """Persist a new session from form data."""

    form_topics: List[TopicInput] = []
    for key, value in request.form.items():
        if key.startswith("topic_name_"):
            uid = key.replace("topic_name_", "")
            note = request.form.get(f"topic_note_{uid}")
            try:
                form_topics.append(TopicInput(name=value, note=note))
            except ValidationError as error:
                flash(str(error), "error")
                return redirect(url_for("new_session"))

    tags_raw = request.form.get("tags", "")
    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]

    payload = {
        "started_at": request.form.get("started_at"),
        "duration_min": request.form.get("duration_min"),
        "instrument_id": request.form.get("instrument_id"),
        "description": request.form.get("description"),
        "topics": form_topics,
        "tags": tags,
    }

    try:
        session_input = SessionInput(
            started_at=parse_datetime(payload["started_at"]),
            duration_min=int(payload["duration_min"]),
            instrument_id=int(payload["instrument_id"]),
            description=payload["description"],
            topics=payload["topics"],
            tags=payload["tags"],
        )
    except (ValueError, ValidationError) as error:
        flash(str(error), "error")
        return redirect(url_for("new_session"))

    instrument = Instrument.query.get(session_input.instrument_id)
    if instrument is None:
        flash("Instrumento no encontrado", "error")
        return redirect(url_for("new_session"))

    session = Session(
        started_at=session_input.started_at,
        duration_min=session_input.duration_min,
        description=session_input.description,
        instrument=instrument,
    )
    db.session.add(session)
    db.session.flush()

    topic_entities = []
    seen_topics = set()
    for topic_input in session_input.topics:
        topic = get_or_create_topic(topic_input.name)
        if topic.id in seen_topics:
            flash(f"El tema '{topic.name}' ya está incluido", "error")
            db.session.rollback()
            return redirect(url_for("new_session"))
        seen_topics.add(topic.id)
        session_topic = SessionTopic(session=session, topic=topic, note=topic_input.note)
        db.session.add(session_topic)
        topic_entities.append(topic)

    tag_entities = [get_or_create_tag(tag_name) for tag_name in session_input.tags]
    for topic in topic_entities:
        for tag in tag_entities:
            existing = TopicTag.query.filter_by(topic_id=topic.id, tag_id=tag.id).one_or_none()
            if existing is None:
                db.session.add(TopicTag(topic=topic, tag=tag))

    db.session.commit()
    flash("Sesión registrada correctamente", "success")
    return redirect(url_for("sessions_list"))


@app.route("/sessions/<int:session_id>")
def session_detail(session_id: int) -> str:
    """Display full session information."""

    session = Session.query.get_or_404(session_id)
    tag_names = [tag.name for tag in Tag.query.order_by(Tag.name)]
    topic_names = [topic.name for topic in Topic.query.order_by(Topic.name)]
    return render_template(
        "session_detail.html",
        session=session,
        tag_names=tag_names,
        topic_names=topic_names,
    )


@app.route("/sessions/<int:session_id>/topics", methods=["POST"])
def add_topic_to_session(session_id: int) -> str:
    """Add a new topic to an existing session via htmx."""

    session = Session.query.get_or_404(session_id)
    name = request.form.get("name", "").strip()
    note = request.form.get("note")
    tags_raw = request.form.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    if not name:
        return Response("<div class='text-red-600'>El tema es obligatorio</div>", status=400)

    topic = get_or_create_topic(name)
    if any(st.topic_id == topic.id for st in session.topics):
        return Response("<div class='text-red-600'>El tema ya existe en la sesión</div>", status=400)
    session_topic = SessionTopic(session=session, topic=topic, note=note)
    db.session.add(session_topic)

    for tag_name in tags:
        tag = get_or_create_tag(tag_name)
        existing = TopicTag.query.filter_by(topic_id=topic.id, tag_id=tag.id).one_or_none()
        if existing is None:
            db.session.add(TopicTag(topic=topic, tag=tag))

    db.session.commit()
    flash("Tema añadido", "success")
    return render_template("_session_topic.html", session_topic=session_topic)


@app.route("/analytics")
def analytics() -> str:
    """Analytics view for aggregated metrics."""

    range_param = request.args.get("range", "7d")
    days = 7 if range_param == "7d" else 30

    since = datetime.now() - timedelta(days=days)
    sessions = (
        Session.query.filter(Session.started_at >= since)
        .order_by(Session.started_at.desc())
        .all()
    )

    total_minutes = sum(session.duration_min for session in sessions)
    streak, streak_start, streak_end = streak_info()
    topic_totals = aggregate_time_by_topic(sessions)
    tag_totals = aggregate_time_by_tag(sessions)

    return render_template(
        "analytics.html",
        range_param=range_param,
        total_minutes=total_minutes,
        streak=streak,
        streak_start=streak_start,
        streak_end=streak_end,
        topic_totals=sorted(topic_totals.items(), key=lambda x: x[1], reverse=True),
        tag_totals=sorted(tag_totals.items(), key=lambda x: x[1], reverse=True),
    )


@app.route("/export.json")
def export_json() -> Response:
    """Export the entire database to JSON."""

    data = {
        "instruments": [
            {"id": inst.id, "name": inst.name} for inst in Instrument.query.all()
        ],
        "tags": [{"id": tag.id, "name": tag.name} for tag in Tag.query.all()],
        "topics": [
            {
                "id": topic.id,
                "name": topic.name,
                "tags": [tt.tag_id for tt in topic.tags],
            }
            for topic in Topic.query.all()
        ],
        "sessions": [serialize_session(session) for session in Session.query.all()],
    }
    return jsonify(data)


@app.route("/export.csv")
def export_csv() -> Response:
    """Export all tables into a lightweight CSV with sections."""

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["# instruments"])
    writer.writerow(["id", "name"])
    for inst in Instrument.query.order_by(Instrument.id):
        writer.writerow([inst.id, inst.name])

    writer.writerow([])
    writer.writerow(["# tags"])
    writer.writerow(["id", "name"])
    for tag in Tag.query.order_by(Tag.id):
        writer.writerow([tag.id, tag.name])

    writer.writerow([])
    writer.writerow(["# topics"])
    writer.writerow(["id", "name"])
    for topic in Topic.query.order_by(Topic.id):
        writer.writerow([topic.id, topic.name])

    writer.writerow([])
    writer.writerow(["# topic_tags"])
    writer.writerow(["topic_id", "tag_id"])
    for topic_tag in TopicTag.query.order_by(TopicTag.topic_id):
        writer.writerow([topic_tag.topic_id, topic_tag.tag_id])

    writer.writerow([])
    writer.writerow(["# sessions"])
    writer.writerow(["id", "started_at", "duration_min", "instrument", "description"])
    for session in Session.query.order_by(Session.started_at):
        writer.writerow(
            [
                session.id,
                session.started_at.isoformat(),
                session.duration_min,
                session.instrument.name,
                (session.description or "").replace("\n", " "),
            ]
        )

    writer.writerow([])
    writer.writerow(["# session_topics"])
    writer.writerow(["session_id", "topic", "note"])
    for session_topic in SessionTopic.query.order_by(SessionTopic.session_id):
        writer.writerow(
            [
                session_topic.session_id,
                session_topic.topic.name,
                (session_topic.note or "").replace("\n", " "),
            ]
        )

    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=practicelog.csv"},
    )


@app.route("/import", methods=["POST"])
def import_json() -> Response:
    """Import JSON data to merge with the current database."""

    file: FileStorage | None = request.files.get("file")
    if file is None or file.filename == "":
        flash("Selecciona un archivo JSON", "error")
        return redirect(request.referrer or url_for("dashboard"))

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".json"):
        flash("El archivo debe ser JSON", "error")
        return redirect(request.referrer or url_for("dashboard"))

    data = json.load(file)

    tag_lookup: Dict[int, Tag] = {}
    for tag_data in data.get("tags", []):
        tag = get_or_create_tag(tag_data["name"])
        tag_lookup[tag_data.get("id", 0)] = tag

    topic_lookup: Dict[int, Topic] = {}
    for topic_data in data.get("topics", []):
        topic = get_or_create_topic(topic_data["name"])
        topic_lookup[topic_data.get("id", 0)] = topic
        for tag_id in topic_data.get("tags", []):
            tag = tag_lookup.get(tag_id)
            if tag is None:
                continue
            existing = TopicTag.query.filter_by(topic_id=topic.id, tag_id=tag.id).one_or_none()
            if existing is None:
                db.session.add(TopicTag(topic=topic, tag=tag))

    instrument_lookup = {inst.name: inst for inst in Instrument.query.all()}
    for instrument_data in data.get("instruments", []):
        name = instrument_data.get("name")
        if name and name not in instrument_lookup:
            instrument = Instrument(name=name)
            db.session.add(instrument)
            db.session.flush()
            instrument_lookup[name] = instrument

    for session_data in data.get("sessions", []):
        started_at = datetime.fromisoformat(session_data["started_at"])
        instrument_name = session_data.get("instrument")
        instrument = instrument_lookup.get(instrument_name)
        if instrument is None:
            instrument = Instrument(name=instrument_name)
            db.session.add(instrument)
            db.session.flush()
            instrument_lookup[instrument_name] = instrument

        session = Session(
            started_at=started_at,
            duration_min=session_data.get("duration_min", 0),
            description=session_data.get("description"),
            instrument=instrument,
        )
        db.session.add(session)
        db.session.flush()

        for topic_info in session_data.get("topics", []):
            topic_name = topic_info.get("name")
            if not topic_name:
                continue
            topic = get_or_create_topic(topic_name)
            session_topic = SessionTopic(
                session=session,
                topic=topic,
                note=topic_info.get("note"),
            )
            db.session.add(session_topic)

            for tag_name in topic_info.get("tags", []):
                tag = get_or_create_tag(tag_name)
                existing = TopicTag.query.filter_by(topic_id=topic.id, tag_id=tag.id).one_or_none()
                if existing is None:
                    db.session.add(TopicTag(topic=topic, tag=tag))

    db.session.commit()
    flash("Importación completada", "success")
    return redirect(request.referrer or url_for("dashboard"))


# API routes ---------------------------------------------------------------
@app.route("/api/sessions")
def api_sessions() -> Response:
    """Return all sessions as JSON."""

    sessions = Session.query.order_by(Session.started_at.desc()).all()
    return jsonify([serialize_session(session) for session in sessions])


@app.route("/api/dashboard")
def api_dashboard() -> Response:
    """Return dashboard metrics as JSON."""

    last_week = weekly_sessions()
    streak, streak_start, streak_end = streak_info()
    topic_totals = aggregate_time_by_topic(last_week)

    return jsonify(
        {
            "streak": streak,
            "streak_start": streak_start.isoformat() if streak_start else None,
            "streak_end": streak_end.isoformat() if streak_end else None,
            "weekly_total": sum(session.duration_min for session in last_week),
            "top_topics": sorted(topic_totals.items(), key=lambda x: x[1], reverse=True)[:5],
        }
    )


@app.context_processor
def inject_now() -> Dict[str, datetime]:
    """Inject the current datetime into templates for convenience."""

    return {"now": datetime.now()}


if __name__ == "__main__":  # pragma: no cover - manual execution
    app.run(debug=True)
