"""SQLite storage for watchlist rows and scan results."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from config import DATABASE_PATH


@dataclass(frozen=True)
class WatchlistItem:
    id: int | None
    title: str
    issue_number: str
    min_grade: float
    max_grade: float
    target_profit_margin: float


@dataclass(frozen=True)
class CandidateListing:
    title: str
    issue_number: str
    grade: float | None
    page_quality: str | None
    fair_value: float
    listing_price: float
    max_buy_price: float
    estimated_profit: float
    estimated_margin: float
    url: str
    source_item_id: str


class Database:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                issue_number TEXT NOT NULL,
                min_grade REAL NOT NULL,
                max_grade REAL NOT NULL,
                target_profit_margin REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                issue_number TEXT NOT NULL,
                grade REAL,
                page_quality TEXT,
                fair_value REAL NOT NULL,
                listing_price REAL NOT NULL,
                max_buy_price REAL NOT NULL,
                estimated_profit REAL NOT NULL,
                estimated_margin REAL NOT NULL,
                url TEXT NOT NULL,
                source_item_id TEXT NOT NULL,
                scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def add_watchlist_item(self, item: WatchlistItem) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO watchlist (title, issue_number, min_grade, max_grade, target_profit_margin)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item.title, item.issue_number, item.min_grade, item.max_grade, item.target_profit_margin),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def delete_watchlist_item(self, item_id: int) -> None:
        self.connection.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
        self.connection.commit()

    def get_watchlist(self) -> list[WatchlistItem]:
        rows = self.connection.execute(
            "SELECT id, title, issue_number, min_grade, max_grade, target_profit_margin FROM watchlist ORDER BY title"
        ).fetchall()
        return [WatchlistItem(**dict(row)) for row in rows]

    def replace_scan_results(self, candidates: Iterable[CandidateListing]) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM scan_results")
            self.connection.executemany(
                """
                INSERT INTO scan_results (
                    title, issue_number, grade, page_quality, fair_value, listing_price,
                    max_buy_price, estimated_profit, estimated_margin, url, source_item_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        candidate.title,
                        candidate.issue_number,
                        candidate.grade,
                        candidate.page_quality,
                        candidate.fair_value,
                        candidate.listing_price,
                        candidate.max_buy_price,
                        candidate.estimated_profit,
                        candidate.estimated_margin,
                        candidate.url,
                        candidate.source_item_id,
                    )
                    for candidate in candidates
                ],
            )

    def close(self) -> None:
        self.connection.close()
