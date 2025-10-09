"""Simple Flask application that displays a table stored in a SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from flask import Flask, render_template

DB_PATH = Path("data.db")


def init_database() -> None:
    """Create the database and populate it with sample data if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                role TEXT NOT NULL
            )
            """
        )

        count = cursor.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        if count == 0:
            cursor.executemany(
                "INSERT INTO employees (first_name, last_name, role) VALUES (?, ?, ?)",
                [
                    ("Ana", "Pérez", "Desarrolladora"),
                    ("Luis", "García", "Diseñador"),
                    ("María", "Rodríguez", "Analista"),
                ],
            )
        connection.commit()


def fetch_employees() -> Iterable[sqlite3.Row]:
    """Retrieve all employees from the database."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            "SELECT id, first_name, last_name, role FROM employees ORDER BY id"
        )
        return cursor.fetchall()


app = Flask(__name__)


@app.before_first_request
def prepare_database() -> None:
    """Ensure the database exists before serving the first request."""
    init_database()


@app.route("/")
def index() -> str:
    employees = fetch_employees()
    return render_template("employees.html", employees=employees)


if __name__ == "__main__":
    init_database()
    app.run(debug=True)
