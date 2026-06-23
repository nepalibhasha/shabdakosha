"""Server-rendered resource browser for generated dictionary artifacts."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from shabdakosha.build_db import build_database
from shabdakosha.romanization import normalize_roman_alias
from shabdakosha.text import normalize_text


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "dictionary.db"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "dictionaries"
DB_BUILD_LOCK = threading.Lock()
DEVANAGARI_TOKEN_RE = re.compile(r"[\u0900-\u097F][\u0900-\u097F\u200c\u200d]*")
VARIANT_SUFFIX_SPACING_RE = re.compile(r"\s+(\([०-९]+\))$")
DEFINITION_LINK_STOPWORDS = {
    "अनि",
    "अर्थात्",
    "आदि",
    "आदिका",
    "आदिको",
    "आदिलाई",
    "आदिले",
    "कि",
    "को",
    "का",
    "की",
    "मा",
    "र",
    "वा",
    "ले",
    "लाई",
    "बाट",
    "भई",
    "भएको",
    "भएका",
    "भन्ने",
    "पनि",
    "प्रायः",
    "जस्तो",
}


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
                WHERE type = 'table' AND name IN ('dictionaries', 'source_entries', 'entries', 'roman_aliases')
                """
            ).fetchall()
    except sqlite3.Error:
        return False
    return {row[0] for row in rows} == {"dictionaries", "source_entries", "entries", "roman_aliases"}


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


def normalize_lookup_text(value: str | None) -> str:
    text = normalize_text(value or "").strip()
    return VARIANT_SUFFIX_SPACING_RE.sub(r"\1", text)


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


def url_quote(value: str | None) -> str:
    if not value:
        return ""
    return quote(value, safe="")


def link_definition(value: str | None) -> Markup:
    if not value:
        return Markup("")
    value = normalize_text(value)

    parts: list[str] = []
    position = 0
    for match in DEVANAGARI_TOKEN_RE.finditer(value):
        parts.append(str(escape(value[position : match.start()])))
        token = match.group(0).rstrip("।॥")
        suffix = match.group(0)[len(token) :]
        if should_link_definition_token(token):
            href = f"/word/{url_quote(token)}"
            parts.append(f'<a class="definition-token" href="{href}">{escape(token)}</a>')
        else:
            parts.append(str(escape(token)))
        parts.append(str(escape(suffix)))
        position = match.end()
    parts.append(str(escape(value[position:])))
    return Markup("".join(parts))


@lru_cache(maxsize=20000)
def lookup_word_exists(word: str) -> bool:
    word = normalize_lookup_text(word)
    if not word:
        return False
    with connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM entries WHERE word = ? LIMIT 1",
            (word,),
        ).fetchone()
    return row is not None


def should_link_definition_token(token: str) -> bool:
    if len(token) < 2 or token in DEFINITION_LINK_STOPWORDS:
        return False
    return lookup_word_exists(token)


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
    text = normalize_lookup_text(query)
    if not text:
        return []
    roman_text = normalize_roman_alias(text)

    filters = []
    rank_params: list[Any] = [
        text,
        text,
        f"{text}%",
        f"{text}%",
        roman_text,
        f"{roman_text}%",
        f"%{text}%",
        f"%{roman_text}%",
    ]
    match_params: list[Any] = [text, text, f"{text}%", f"{text}%", f"%{text}%", f"%{text}%"]
    alias_params: list[Any] = [roman_text, f"{roman_text}%", f"%{roman_text}%"]
    filter_params: list[Any] = []
    if dictionary_id:
        filters.append("e.dictionary_id = ?")
        filter_params.append(dictionary_id)
    direct_where = "(e.word = ? OR e.base_word = ? OR e.word LIKE ? OR e.base_word LIKE ? OR e.word LIKE ? OR e.base_word LIKE ?)"
    alias_where = "(? != '' AND (ra.alias = ? OR ra.alias LIKE ? OR ra.alias LIKE ?))"
    where = " AND ".join([f"({direct_where} OR {alias_where})"] + filters)

    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                e.dictionary_id,
                e.word,
                e.base_word,
                e.variant_number,
                e.part_of_speech,
                e.definition,
                e.source_file,
                e.entry_kind,
                s.display_headword,
                COALESCE(
                    MAX(CASE WHEN ra.alias = ? THEN ra.alias END),
                    MAX(CASE WHEN ra.alias LIKE ? THEN ra.alias END),
                    MAX(CASE WHEN ra.alias LIKE ? THEN ra.alias END)
                ) AS matched_roman_alias,
                COALESCE(
                    MAX(CASE WHEN ra.alias = ? THEN ra.weight END),
                    MAX(CASE WHEN ra.alias LIKE ? THEN ra.weight END),
                    MAX(CASE WHEN ra.alias LIKE ? THEN ra.weight END)
                ) AS matched_roman_weight,
                MIN(CASE
                    WHEN e.word = ? THEN 0
                    WHEN e.base_word = ? THEN 1
                    WHEN e.word LIKE ? THEN 2
                    WHEN e.base_word LIKE ? THEN 3
                    WHEN ra.alias = ? THEN 4
                    WHEN ra.alias LIKE ? THEN 5
                    WHEN e.word LIKE ? THEN 4
                    WHEN ra.alias LIKE ? THEN 6
                    ELSE 7
                END) AS rank
            FROM entries e
            JOIN source_entries s ON s.id = e.source_entry_id
            LEFT JOIN roman_aliases ra ON ra.entry_id = e.id
            WHERE {where}
            GROUP BY e.id
            ORDER BY rank, matched_roman_weight DESC, e.dictionary_id, e.base_word, e.variant_number IS NOT NULL, e.variant_number, e.word
            LIMIT ?
            """,
            alias_params + alias_params + rank_params + match_params + [roman_text] + alias_params + filter_params + [limit],
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def grouped_search(
    query: str,
    dictionary_id: str | None = None,
    limit: int = 90,
) -> list[dict[str, Any]]:
    text = normalize_lookup_text(query)
    rows = search_entries(query, dictionary_id=dictionary_id, limit=limit)
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        lookup_word = (
            row["base_word"]
            if row["base_word"] == text and row["word"] != text
            else row["word"]
        )
        group = groups.setdefault(
            lookup_word,
            {
                "lookup_word": lookup_word,
                "base_word": lookup_word,
                "rank": row["rank"],
                "matched_roman_alias": row.get("matched_roman_alias"),
                "matched_roman_weight": row.get("matched_roman_weight"),
                "dictionaries": set(),
                "entries": [],
            },
        )
        group["rank"] = min(group["rank"], row["rank"])
        if row.get("matched_roman_weight") is not None and (
            group.get("matched_roman_weight") is None
            or row["matched_roman_weight"] > group["matched_roman_weight"]
        ):
            group["matched_roman_alias"] = row.get("matched_roman_alias")
            group["matched_roman_weight"] = row.get("matched_roman_weight")
        group["dictionaries"].add(row["dictionary_id"])
        group["entries"].append(row)

    grouped = list(groups.values())
    for group in grouped:
        group["dictionaries"] = sorted(group["dictionaries"])
    grouped.sort(key=lambda item: (item["rank"], item["lookup_word"]))
    return grouped


def get_entry(dictionary_id: str, word: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT e.*, s.display_headword
            FROM entries e
            JOIN source_entries s ON s.id = e.source_entry_id
            WHERE e.dictionary_id = ? AND e.word = ?
            """,
            (dictionary_id, normalize_lookup_text(word)),
        ).fetchone()
    if row is None:
        return None
    entry = row_to_dict(row)
    entry["split_definitions"] = parse_json(entry.get("split_definitions")) or []
    return entry


def compare_lookup_word(lookup_word: str) -> list[dict[str, Any]]:
    lookup_word = normalize_lookup_text(lookup_word)
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT e.*, s.display_headword
            FROM entries e
            JOIN source_entries s ON s.id = e.source_entry_id
            WHERE e.word = ? OR e.base_word = ?
            ORDER BY
                CASE WHEN e.word = ? THEN 0 ELSE 1 END,
                e.dictionary_id,
                e.variant_number IS NOT NULL,
                e.variant_number,
                e.word
            """,
            (lookup_word, lookup_word, lookup_word),
        ).fetchall()
    entries = []
    for row in rows:
        entry = row_to_dict(row)
        entry["split_definitions"] = parse_json(entry.get("split_definitions")) or []
        entries.append(entry)
    return entries


def get_word_groups(lookup_word: str) -> dict[str, Any]:
    lookup_word = normalize_lookup_text(lookup_word)
    entries = compare_lookup_word(lookup_word)
    by_dictionary: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_dictionary.setdefault(entry["dictionary_id"], []).append(entry)
    return {
        "base_word": lookup_word,
        "lookup_word": lookup_word,
        "entries": entries,
        "by_dictionary": by_dictionary,
        "dictionary_ids": sorted(by_dictionary),
    }


def suggest_words(query: str, dictionary_id: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
    text = normalize_lookup_text(query)
    if not text:
        return []
    roman_text = normalize_roman_alias(text)

    filters = []
    rank_params: list[Any] = [text, text, f"{text}%", roman_text, f"{roman_text}%"]
    match_params: list[Any] = [text, text, f"{text}%", f"{text}%"]
    alias_params: list[Any] = [roman_text, f"{roman_text}%"]
    filter_params: list[Any] = []
    if dictionary_id:
        filters.append("e.dictionary_id = ?")
        filter_params.append(dictionary_id)
    direct_where = "(e.word = ? OR e.base_word = ? OR e.word LIKE ? OR e.base_word LIKE ?)"
    alias_where = "(? != '' AND (ra.alias = ? OR ra.alias LIKE ?))"
    where = " AND ".join([f"({direct_where} OR {alias_where})"] + filters)

    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                e.word,
                MIN(e.base_word) AS base_word,
                MIN(s.display_headword) AS display_headword,
                COALESCE(
                    MAX(CASE WHEN ra.alias = ? THEN ra.alias END),
                    MAX(CASE WHEN ra.alias LIKE ? THEN ra.alias END)
                ) AS matched_roman_alias,
                MIN(CASE
                    WHEN e.word = ? THEN 0
                    WHEN e.base_word = ? THEN 1
                    WHEN e.word LIKE ? THEN 2
                    WHEN ra.alias = ? THEN 3
                    WHEN ra.alias LIKE ? THEN 4
                    ELSE 3
                END) AS rank,
                MAX(CASE
                    WHEN ra.alias = ? THEN ra.weight
                    WHEN ra.alias LIKE ? THEN ra.weight
                    ELSE NULL
                END) AS matched_roman_weight,
                COUNT(*) AS entry_count,
                GROUP_CONCAT(DISTINCT e.dictionary_id) AS dictionary_ids
            FROM entries e
            JOIN source_entries s ON s.id = e.source_entry_id
            LEFT JOIN roman_aliases ra ON ra.entry_id = e.id
            WHERE {where}
            GROUP BY e.word
            ORDER BY rank, matched_roman_weight DESC, e.word
            LIMIT ?
            """,
            alias_params + rank_params + alias_params + match_params + [roman_text] + alias_params + filter_params + [limit],
        ).fetchall()

    suggestions = []
    for row in rows:
        item = row_to_dict(row)
        item["dictionary_ids"] = sorted((item.get("dictionary_ids") or "").split(","))
        suggestions.append(item)
    return suggestions


def create_app() -> FastAPI:
    app = FastAPI(title="Shabdakosha Resource Browser")
    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    templates.env.filters["parse_json"] = parse_json
    templates.env.filters["format_count"] = format_count
    templates.env.filters["summarize"] = summarize
    templates.env.filters["url_quote"] = url_quote
    templates.env.filters["link_definition"] = link_definition
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
        query = q.strip()
        return templates.TemplateResponse(
            request,
            "search.html",
            {
                "q": query,
                "dictionary_id": dictionary_id,
                "dictionaries": get_dictionaries(),
                "groups": grouped_search(query, dictionary_id=dictionary_id),
            },
        )

    @app.get("/api/suggest")
    def suggest(q: str = "", dictionary_id: str | None = Query(default=None)) -> dict[str, Any]:
        return {"suggestions": suggest_words(q, dictionary_id=dictionary_id)}

    @app.get("/word/{base_word:path}", response_class=HTMLResponse)
    def word(request: Request, base_word: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "word.html",
            {
                "word": get_word_groups(base_word),
                "dictionaries": get_dictionaries(),
            },
        )

    @app.get("/entry/{dictionary_id}/{word:path}", response_class=HTMLResponse)
    def entry(request: Request, dictionary_id: str, word: str) -> HTMLResponse:
        found = get_entry(dictionary_id, word)
        return templates.TemplateResponse(
            request,
            "entry.html",
            {
                "entry": found,
                "dictionaries": get_dictionaries(),
            },
            status_code=200 if found else 404,
        )

    @app.get("/compare/{base_word:path}", response_class=HTMLResponse)
    def compare(request: Request, base_word: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "compare.html",
            {
                "base_word": base_word,
                "entries": compare_lookup_word(base_word),
                "dictionaries": get_dictionaries(),
            },
        )

    return app


app = create_app()
