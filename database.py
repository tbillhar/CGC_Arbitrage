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
    listing_flags: str
    fair_value: float
    fair_value_source: str
    listing_price: float
    max_buy_price: float
    estimated_profit: float
    estimated_margin: float
    url: str
    source_item_id: str
    seller_username: str


@dataclass(frozen=True)
class AppSettings:
    selling_fee_rate: float
    payment_fee_rate: float
    shipping_cost: float
    default_profit_margin: float


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
                listing_flags TEXT NOT NULL DEFAULT '',
                fair_value REAL NOT NULL,
                fair_value_source TEXT NOT NULL DEFAULT '',
                listing_price REAL NOT NULL,
                max_buy_price REAL NOT NULL,
                estimated_profit REAL NOT NULL,
                estimated_margin REAL NOT NULL,
                url TEXT NOT NULL,
                source_item_id TEXT NOT NULL,
                seller_username TEXT NOT NULL DEFAULT '',
                scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self._ensure_scan_result_column("fair_value_source", "TEXT NOT NULL DEFAULT ''")
        self._ensure_scan_result_column("seller_username", "TEXT NOT NULL DEFAULT ''")
        self._ensure_scan_result_column("listing_flags", "TEXT NOT NULL DEFAULT ''")
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

    def add_watchlist_items(self, items: Iterable[WatchlistItem]) -> int:
        existing = {
            self._watchlist_key(item)
            for item in self.get_watchlist()
        }
        rows_to_insert = []
        for item in items:
            key = self._watchlist_key(item)
            if key in existing:
                continue
            existing.add(key)
            rows_to_insert.append(
                (item.title, item.issue_number, item.min_grade, item.max_grade, item.target_profit_margin)
            )

        if not rows_to_insert:
            return 0

        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO watchlist (title, issue_number, min_grade, max_grade, target_profit_margin)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows_to_insert,
            )
        return len(rows_to_insert)

    def delete_watchlist_item(self, item_id: int) -> None:
        self.connection.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
        self.connection.commit()

    def get_watchlist(self) -> list[WatchlistItem]:
        rows = self.connection.execute(
            "SELECT id, title, issue_number, min_grade, max_grade, target_profit_margin FROM watchlist ORDER BY title"
        ).fetchall()
        return [WatchlistItem(**dict(row)) for row in rows]

    def get_app_settings(self) -> dict[str, str]:
        rows = self.connection.execute("SELECT key, value FROM app_settings").fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

    def save_app_settings(self, settings: AppSettings) -> None:
        rows = [
            ("selling_fee_rate", str(settings.selling_fee_rate)),
            ("payment_fee_rate", str(settings.payment_fee_rate)),
            ("shipping_cost", str(settings.shipping_cost)),
            ("default_profit_margin", str(settings.default_profit_margin)),
        ]
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                rows,
            )

    def replace_scan_results(self, candidates: Iterable[CandidateListing]) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM scan_results")
            self.connection.executemany(
                """
                INSERT INTO scan_results (
                    title, issue_number, grade, page_quality, listing_flags, fair_value,
                    fair_value_source, listing_price, max_buy_price, estimated_profit,
                    estimated_margin, url, source_item_id, seller_username
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        candidate.title,
                        candidate.issue_number,
                        candidate.grade,
                        candidate.page_quality,
                        candidate.listing_flags,
                        candidate.fair_value,
                        candidate.fair_value_source,
                        candidate.listing_price,
                        candidate.max_buy_price,
                        candidate.estimated_profit,
                        candidate.estimated_margin,
                        candidate.url,
                        candidate.source_item_id,
                        candidate.seller_username,
                    )
                    for candidate in candidates
                ],
            )

    def close(self) -> None:
        self.connection.close()

    def _watchlist_key(self, item: WatchlistItem) -> tuple[str, str, float, float, float]:
        return (
            item.title.strip().casefold(),
            item.issue_number.strip().casefold(),
            round(item.min_grade, 1),
            round(item.max_grade, 1),
            round(item.target_profit_margin, 4),
        )

    def _ensure_scan_result_column(self, column_name: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(scan_results)").fetchall()
        }
        if column_name not in columns:
            self.connection.execute(f"ALTER TABLE scan_results ADD COLUMN {column_name} {definition}")
