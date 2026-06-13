"""Server-rendered resource browser for generated dictionary artifacts."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shabdakosha.build_db import build_database


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "dictionary.db"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "dictionaries"
DB_BUILD_LOCK = threading.Lock()


def db_path() -> Path:
    return Path(os.environ.get("SHABDAKOSHA_DB_PATH", DEFAULT_DB_PATH)).expanduser()


def data_dir() -> Path:
    return Path(os.environ.get("SHABDAKOSHA_DATA_DIR", DEFAULT_DATA_DIR)).expanduser()


def ensure_database() -> None:
    path = db_path()
    if database_ready(path):
        return
    with DB_BUILD_LOCK:
        if database_ready(path):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        if tmp_path.exists():
            tmp_path.unlink()
        build_database(data_dir(), tmp_path)
        tmp_path.replace(path)


def database_ready(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name IN ('dictionaries', 'entries')
                """
            ).fetchall()
    except sqlite3.Error:
        return False
    return {row[0] for row in rows} == {"dictionaries", "entries"}


def connection() -> sqlite3.Connection:
    ensure_database()
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def parse_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def format_count(value: int | None) -> str:
    if value is None:
        return "0"
    return f"{value:,}"


def summarize(value: str | None, limit: int = 220) -> str:
    if not value:
        return ""
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def get_dictionaries() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.name,
                d.name_en,
                d.source_language,
                d.target_language,
                d.script,
                d.metadata_json,
                COUNT(e.id) AS entry_count,
                COUNT(DISTINCT e.base_word) AS base_word_count
            FROM dictionaries d
            LEFT JOIN entries e ON e.dictionary_id = d.id
            GROUP BY d.id
            ORDER BY d.id
            """
        ).fetchall()
    dictionaries = []
    for row in rows:
        item = row_to_dict(row)
        item["metadata"] = parse_json(item.pop("metadata_json"))
        dictionaries.append(item)
    return dictionaries


def get_stats() -> dict[str, int]:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS entry_count,
                COUNT(DISTINCT base_word) AS base_word_count,
                COUNT(DISTINCT dictionary_id) AS dictionary_count
            FROM entries
            """
        ).fetchone()
    return row_to_dict(row)


def search_entries(
    query: str,
    dictionary_id: str | None = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    text = query.strip()
    if not text:
        return []

    filters = []
    rank_params: list[Any] = [text, text, f"{text}%", f"{text}%", f"%{text}%"]
    match_params: list[Any] = [text, text, f"{text}%", f"{text}%", f"%{text}%", f"%{text}%"]
    filter_params: list[Any] = []
    if dictionary_id:
        filters.append("dictionary_id = ?")
        filter_params.append(dictionary_id)
    where = " AND ".join(["(word = ? OR base_word = ? OR word LIKE ? OR base_word LIKE ? OR word LIKE ? OR base_word LIKE ?)"] + filters)

    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                dictionary_id,
                word,
                base_word,
                variant_number,
                part_of_speech,
                definition,
                source_file,
                CASE
                    WHEN word = ? THEN 0
                    WHEN base_word = ? THEN 1
                    WHEN word LIKE ? THEN 2
                    WHEN base_word LIKE ? THEN 3
                    WHEN word LIKE ? THEN 4
                    ELSE 5
                END AS rank
            FROM entries
            WHERE {where}
            ORDER BY rank, dictionary_id, base_word, variant_number IS NOT NULL, variant_number, word
            LIMIT ?
            """,
            rank_params + match_params + filter_params + [limit],
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_entry(dictionary_id: str, word: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM entries
            WHERE dictionary_id = ? AND word = ?
            """,
            (dictionary_id, word),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry = row_to_dict(row)
    entry["split_definitions"] = parse_json(entry.get("split_definitions")) or []
    return entry


def compare_base_word(base_word: str) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM entries
            WHERE base_word = ?
            ORDER BY dictionary_id, variant_number IS NOT NULL, variant_number, word
            """,
            (base_word,),
        ).fetchall()
    entries = []
    for row in rows:
        entry = row_to_dict(row)
        entry["split_definitions"] = parse_json(entry.get("split_definitions")) or []
        entries.append(entry)
    return entries


def create_app() -> FastAPI:
    app = FastAPI(title="Shabdakosha Resource Browser")
    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    templates.env.filters["parse_json"] = parse_json
    templates.env.filters["format_count"] = format_count
    templates.env.filters["summarize"] = summarize
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        ensure_database()
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "dictionaries": get_dictionaries(),
                "stats": get_stats(),
            },
        )

    @app.get("/search", response_class=HTMLResponse)
    def search(
        request: Request,
        q: str = "",
        dictionary_id: str | None = Query(default=None),
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "search.html",
            {
                "q": q.strip(),
                "dictionary_id": dictionary_id,
                "dictionaries": get_dictionaries(),
                "results": search_entries(q, dictionary_id=dictionary_id),
            },
        )

    @app.get("/entry/{dictionary_id}/{word:path}", response_class=HTMLResponse)
    def entry(request: Request, dictionary_id: str, word: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "entry.html",
            {
                "entry": get_entry(dictionary_id, word),
                "dictionaries": get_dictionaries(),
            },
        )

    @app.get("/compare/{base_word:path}", response_class=HTMLResponse)
    def compare(request: Request, base_word: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "compare.html",
            {
                "base_word": base_word,
                "entries": compare_base_word(base_word),
                "dictionaries": get_dictionaries(),
            },
        )

    return app


app = create_app()
